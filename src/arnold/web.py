from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from flask import Flask, redirect, render_template, request, url_for

from arnold.models import Card, Deck, Rating, Selection
from arnold.scheduler import apply_rating, select_next, unix_now
from arnold.state import StateStore


def _is_htmx_request() -> bool:
    return request.headers.get("HX-Request") == "true"


def _format_local_time(ts: int) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


@dataclass(frozen=True, slots=True)
class AppConfig:
    decks: tuple[Deck, ...]
    state_store: StateStore
    state_lock: threading.Lock
    now_fn: Callable[[], int]
    cards_by_key: dict[str, Card]


def create_app(
    *,
    decks: list[Deck],
    state_store: StateStore,
    now_fn: Callable[[], int] = unix_now,
) -> Flask:
    app = Flask(__name__)

    cards_by_key: dict[str, Card] = {}
    for deck in decks:
        for card in deck.cards:
            cards_by_key[card.key] = card

    cfg = AppConfig(
        decks=tuple(decks),
        state_store=state_store,
        state_lock=threading.Lock(),
        now_fn=now_fn,
        cards_by_key=cards_by_key,
    )

    def render_study(
        *,
        selection: Selection,
        done_count: int,
        revealed: bool = False,
        revealed_card: Card | None = None,
    ):
        card = revealed_card if revealed else selection.card
        next_due_str = (
            _format_local_time(selection.next_due) if selection.next_due is not None else None
        )

        template = "study_pane.html" if _is_htmx_request() else "study.html"
        return render_template(
            template,
            htmx=_is_htmx_request(),
            deck_count=len(cfg.decks),
            total_count=selection.total_count,
            due_count=selection.due_count,
            new_count=selection.new_count,
            done_count=done_count,
            card=card,
            revealed=revealed,
            next_due_str=next_due_str,
        )

    def current_snapshot() -> tuple[Selection, int]:
        now = cfg.now_fn()
        with cfg.state_lock:
            selection = select_next(decks=cfg.decks, state=cfg.state_store.cards, now=now)
            return selection, cfg.state_store.reviews_done

    @app.get("/")
    def study() -> str:
        selection, done_count = current_snapshot()
        return render_study(selection=selection, done_count=done_count, revealed=False)

    @app.post("/reveal")
    def reveal() -> str:
        card_key = request.form.get("card_key", "")
        card = cfg.cards_by_key.get(card_key)

        selection, done_count = current_snapshot()
        if card is None:
            if _is_htmx_request():
                return render_study(selection=selection, done_count=done_count, revealed=False)
            return redirect(url_for("study"))

        return render_study(
            selection=selection,
            done_count=done_count,
            revealed=True,
            revealed_card=card,
        )

    @app.post("/rate")
    def rate():
        card_key = request.form.get("card_key", "")
        rating_raw = request.form.get("rating", "")
        rating: Rating
        if rating_raw in ("again", "hard", "good", "easy"):
            rating = rating_raw  # type: ignore[assignment]
        else:
            if _is_htmx_request():
                selection, done_count = current_snapshot()
                return render_study(selection=selection, done_count=done_count, revealed=False), 400
            return redirect(url_for("study"))

        if card_key not in cfg.cards_by_key:
            if _is_htmx_request():
                selection, done_count = current_snapshot()
                return render_study(selection=selection, done_count=done_count, revealed=False), 400
            return redirect(url_for("study"))

        now = cfg.now_fn()
        with cfg.state_lock:
            cfg.state_store.cards[card_key] = apply_rating(
                existing=cfg.state_store.cards.get(card_key),
                rating=rating,
                now=now,
            )
            cfg.state_store.reviews_done += 1
            cfg.state_store.save(now=now)
            selection = select_next(decks=cfg.decks, state=cfg.state_store.cards, now=now)
            done_count = cfg.state_store.reviews_done

        if _is_htmx_request():
            return render_study(selection=selection, done_count=done_count, revealed=False)
        return redirect(url_for("study"))

    return app


def default_state_path() -> Path:
    return Path("arnold_state.json")
