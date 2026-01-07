from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from flask import Flask, redirect, render_template, request, url_for

from arnold.models import Card, CardState, Deck, Rating, Selection
from arnold.scheduler import apply_rating, select_next, unix_now
from arnold.state import StateStore


def _is_htmx_request() -> bool:
    return request.headers.get("HX-Request") == "true"


def _format_local_time(ts: int) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %I:%M %p")


def _format_sleep_seconds(seconds: int) -> str:
    seconds = max(0, int(seconds))
    if seconds < 90:
        return "1m"
    if seconds < 60 * 60:
        minutes = max(1, int(round(seconds / 60)))
        return f"{minutes}m"
    if seconds < 24 * 60 * 60:
        hours = max(1, int(round(seconds / (60 * 60))))
        return f"{hours}h"
    days = seconds / (24 * 60 * 60)
    rounded = round(days)
    if abs(days - rounded) >= 0.05 and days < 10:
        return f"{days:.1f}d".rstrip("0").rstrip(".")
    return f"{max(1, int(rounded))}d"


def _rating_previews(*, existing: CardState | None, now: int) -> dict[Rating, str]:
    previews: dict[Rating, str] = {}
    ratings: tuple[Rating, ...] = ("again", "hard", "good", "easy")
    for rating in ratings:
        next_state = apply_rating(existing=existing, rating=rating, now=now)
        previews[rating] = _format_sleep_seconds(next_state.due - now)
    return previews


@dataclass(frozen=True, slots=True)
class AppConfig:
    decks: tuple[Deck, ...]
    state_store: StateStore
    state_lock: threading.Lock
    session: "SessionStats"
    now_fn: Callable[[], int]
    cards_by_key: dict[str, Card]


@dataclass(slots=True)
class SessionStats:
    done_count: int = 0


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
        session=SessionStats(),
        now_fn=now_fn,
        cards_by_key=cards_by_key,
    )

    def render_study(
        *,
        selection: Selection,
        done_count: int,
        revealed: bool = False,
        revealed_card: Card | None = None,
        rating_previews: dict[Rating, str] | None = None,
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
            rating_previews=rating_previews,
        )

    def current_snapshot() -> tuple[Selection, int]:
        now = cfg.now_fn()
        with cfg.state_lock:
            selection = select_next(decks=cfg.decks, state=cfg.state_store.cards, now=now)
            return selection, cfg.session.done_count

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

        now = cfg.now_fn()
        with cfg.state_lock:
            existing = cfg.state_store.cards.get(card_key)

        return render_study(
            selection=selection,
            done_count=done_count,
            revealed=True,
            revealed_card=card,
            rating_previews=_rating_previews(existing=existing, now=now),
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
            cfg.session.done_count += 1
            cfg.state_store.save(now=now)
            selection = select_next(decks=cfg.decks, state=cfg.state_store.cards, now=now)
            done_count = cfg.session.done_count

        if _is_htmx_request():
            return render_study(selection=selection, done_count=done_count, revealed=False)
        return redirect(url_for("study"))

    return app


def default_state_path() -> Path:
    return Path("arnold_state.json")
