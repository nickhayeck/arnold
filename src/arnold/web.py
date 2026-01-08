from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Literal

from flask import Flask, redirect, render_template, request, url_for

from arnold.models import Card, CardState, Deck, Rating, Selection
from arnold.scheduler import apply_rating, select_next, unix_now
from arnold.state import StateStore

RATINGS: dict[str, Rating] = {
    "again": "again",
    "hard": "hard",
    "good": "good",
    "easy": "easy",
}

StudyMode = Literal["study", "history"]


def _is_htmx_request() -> bool:
    """Return True if this request was initiated by htmx (via `HX-Request: true`)."""
    return request.headers.get("HX-Request") == "true"


def _format_local_time(ts: int) -> str:
    """Format a unix timestamp using the server's local timezone."""
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %I:%M %p")


def _format_sleep_seconds(seconds: int) -> str:
    """Human-friendly duration label for rating previews."""
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
    """Compute preview sleep times for each rating button."""
    previews: dict[Rating, str] = {}
    ratings: tuple[Rating, ...] = ("again", "hard", "good", "easy")
    for rating in ratings:
        next_state = apply_rating(existing=existing, rating=rating, now=now)
        previews[rating] = _format_sleep_seconds(next_state.due - now)
    return previews


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    """One answered card in this server session (enables back/next + undo)."""

    card_key: str
    rating: Rating
    previous_state: CardState | None


@dataclass(slots=True)
class SessionState:
    """Ephemeral per-process session state.

    `history_cursor` counts how many steps back the user is:
    - 0 => current (normal study flow)
    - 1 => most recently answered card
    - N => Nth most recently answered card
    """

    done_count: int = 0
    history: list[HistoryEntry] = field(default_factory=list)
    history_cursor: int = 0


@dataclass(frozen=True, slots=True)
class StudySnapshot:
    """A consistent snapshot for rendering the study view."""

    selection: Selection
    done_count: int
    history_cursor: int
    history_len: int


@dataclass(frozen=True, slots=True)
class AppConfig:
    decks: tuple[Deck, ...]
    state_store: StateStore
    state_lock: threading.Lock
    session: SessionState
    now_fn: Callable[[], int]
    cards_by_key: dict[str, Card]


def create_app(
    *,
    decks: list[Deck],
    state_store: StateStore,
    now_fn: Callable[[], int] = unix_now,
) -> Flask:
    """Create the Flask app used by `arnold`.

    Notes:
    - The app is local-first; progress lives in `state_store`.
    - `now_fn` is injectable for deterministic tests.
    - Session-only features (Done count, history, undo) are stored in memory.
    """
    app = Flask(__name__)

    cards_by_key: dict[str, Card] = {}
    for deck in decks:
        for card in deck.cards:
            cards_by_key[card.key] = card

    cfg = AppConfig(
        decks=tuple(decks),
        state_store=state_store,
        state_lock=threading.Lock(),
        session=SessionState(),
        now_fn=now_fn,
        cards_by_key=cards_by_key,
    )

    def _reset_history_cursor() -> None:
        with cfg.state_lock:
            cfg.session.history_cursor = 0

    def _move_history_cursor(delta: int) -> None:
        """Move the session history cursor, clamped to `[0, len(history)]`."""
        with cfg.state_lock:
            history_len = len(cfg.session.history)
            if history_len == 0:
                cfg.session.history_cursor = 0
                return
            cfg.session.history_cursor = max(
                0, min(history_len, cfg.session.history_cursor + delta)
            )

    def _snapshot(*, now: int) -> StudySnapshot:
        """Read a consistent view snapshot (selection + history cursor/len + done)."""
        with cfg.state_lock:
            history_len = len(cfg.session.history)
            history_cursor = min(cfg.session.history_cursor, history_len)
            cfg.session.history_cursor = history_cursor
            selection = select_next(
                decks=cfg.decks, state=cfg.state_store.cards, now=now
            )
            done_count = cfg.session.done_count
        return StudySnapshot(
            selection=selection,
            done_count=done_count,
            history_cursor=history_cursor,
            history_len=history_len,
        )

    def _history_card_for_cursor(*, history_cursor: int) -> Card | None:
        """Return the card at `history_cursor`, or None if out of bounds."""
        if history_cursor <= 0:
            return None
        with cfg.state_lock:
            history_len = len(cfg.session.history)
            if history_cursor > history_len:
                return None
            idx = history_len - history_cursor
            entry = cfg.session.history[idx]
        return cfg.cards_by_key.get(entry.card_key)

    def _render_study(
        *,
        snapshot: StudySnapshot,
        revealed: bool = False,
        revealed_card: Card | None = None,
        rating_previews: dict[Rating, str] | None = None,
        mode: StudyMode = "study",
    ):
        htmx = _is_htmx_request()
        card = revealed_card if revealed else snapshot.selection.card
        next_due_str = (
            _format_local_time(snapshot.selection.next_due)
            if snapshot.selection.next_due is not None
            else None
        )
        can_go_back = snapshot.history_len > 0 and snapshot.history_cursor < snapshot.history_len
        can_go_next = snapshot.history_cursor > 0
        can_undo = snapshot.history_len > 0

        template = "study_pane.html" if htmx else "study.html"
        return render_template(
            template,
            htmx=htmx,
            due_count=snapshot.selection.due_count,
            new_count=snapshot.selection.new_count,
            done_count=snapshot.done_count,
            card=card,
            revealed=revealed,
            next_due_str=next_due_str,
            rating_previews=rating_previews,
            mode=mode,
            history_cursor=snapshot.history_cursor,
            history_len=snapshot.history_len,
            can_go_back=can_go_back,
            can_go_next=can_go_next,
            can_undo=can_undo,
        )

    def _render_history_view(*, now: int, snapshot: StudySnapshot) -> str:
        """Render the current history card, or fall back to the live study view."""
        history_card = _history_card_for_cursor(history_cursor=snapshot.history_cursor)
        if history_card is None:
            _reset_history_cursor()
            snapshot = _snapshot(now=now)
            return _render_study(snapshot=snapshot, revealed=False, mode="study")

        return _render_study(
            snapshot=snapshot,
            revealed=True,
            revealed_card=history_card,
            mode="history",
        )

    @app.get("/")
    def study() -> str:
        now = cfg.now_fn()
        _reset_history_cursor()
        snapshot = _snapshot(now=now)
        return _render_study(snapshot=snapshot, revealed=False, mode="study")

    @app.post("/reveal")
    def reveal() -> str:
        htmx = _is_htmx_request()
        now = cfg.now_fn()
        card_key = request.form.get("card_key", "")
        card = cfg.cards_by_key.get(card_key)

        _reset_history_cursor()
        snapshot = _snapshot(now=now)
        if card is None:
            if htmx:
                return _render_study(snapshot=snapshot, revealed=False, mode="study")
            return redirect(url_for("study"))

        with cfg.state_lock:
            existing = cfg.state_store.cards.get(card_key)

        return _render_study(
            snapshot=snapshot,
            revealed=True,
            revealed_card=card,
            rating_previews=_rating_previews(existing=existing, now=now),
            mode="study",
        )

    @app.post("/rate")
    def rate():
        htmx = _is_htmx_request()
        card_key = request.form.get("card_key", "")
        rating = RATINGS.get(request.form.get("rating", ""))
        if rating is None or card_key not in cfg.cards_by_key:
            if not htmx:
                return redirect(url_for("study"))

            now = cfg.now_fn()
            _reset_history_cursor()
            snapshot = _snapshot(now=now)
            return _render_study(snapshot=snapshot, revealed=False, mode="study"), 400

        now = cfg.now_fn()
        with cfg.state_lock:
            cfg.session.history_cursor = 0
            previous_state = cfg.state_store.cards.get(card_key)
            cfg.state_store.cards[card_key] = apply_rating(
                existing=previous_state,
                rating=rating,
                now=now,
            )
            cfg.session.history.append(
                HistoryEntry(
                    card_key=card_key,
                    rating=rating,
                    previous_state=previous_state,
                )
            )
            cfg.session.done_count += 1
            cfg.state_store.save(now=now)

        snapshot = _snapshot(now=now)
        if htmx:
            return _render_study(snapshot=snapshot, revealed=False, mode="study")
        return redirect(url_for("study"))

    @app.post("/history/back")
    def history_back() -> str:
        now = cfg.now_fn()
        _move_history_cursor(+1)
        snapshot = _snapshot(now=now)
        return _render_history_view(now=now, snapshot=snapshot)

    @app.post("/history/next")
    def history_next() -> str:
        now = cfg.now_fn()
        _move_history_cursor(-1)
        snapshot = _snapshot(now=now)
        if snapshot.history_cursor <= 0:
            return _render_study(snapshot=snapshot, revealed=False, mode="study")
        return _render_history_view(now=now, snapshot=snapshot)

    @app.post("/undo")
    def undo():
        now = cfg.now_fn()
        with cfg.state_lock:
            cfg.session.history_cursor = 0
            entry = cfg.session.history.pop() if cfg.session.history else None

            restored_state: CardState | None
            if entry is None:
                restored_state = None
            elif entry.previous_state is None:
                cfg.state_store.cards.pop(entry.card_key, None)
                restored_state = None
            else:
                cfg.state_store.cards[entry.card_key] = entry.previous_state
                restored_state = entry.previous_state

            if entry is not None:
                cfg.session.done_count = max(0, cfg.session.done_count - 1)
                cfg.state_store.save(now=now)

        snapshot = _snapshot(now=now)
        if entry is None:
            return _render_study(snapshot=snapshot, revealed=False, mode="study"), 400

        card = cfg.cards_by_key.get(entry.card_key)
        if card is None:
            return _render_study(snapshot=snapshot, revealed=False, mode="study")

        return _render_study(
            snapshot=snapshot,
            revealed=True,
            revealed_card=card,
            rating_previews=_rating_previews(existing=restored_state, now=now),
            mode="study",
        )

    return app
