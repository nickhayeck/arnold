from __future__ import annotations

import time
from typing import Iterable

from arnold.models import Card, CardState, Deck, Rating, Selection

DEFAULT_EASE = 2.5
MIN_EASE = 1.3


def unix_now() -> int:
    """Return the current unix timestamp in seconds."""
    return int(time.time())


def default_state(*, now: int) -> CardState:
    """Return the initial scheduling state for a new card."""
    return CardState(
        due=now, interval_days=0.0, ease_factor=DEFAULT_EASE, repetitions=0
    )


def apply_rating(*, existing: CardState | None, rating: Rating, now: int) -> CardState:
    """Apply a rating to the existing state and return the next state."""
    state = existing if existing is not None else default_state(now=now)

    ease = state.ease_factor
    reps = state.repetitions
    interval = state.interval_days

    if rating == "again":
        ease = max(MIN_EASE, ease - 0.2)
        reps = 0
        interval = 0.0
        due = now + 60
    elif rating == "hard":
        ease = max(MIN_EASE, ease - 0.15)
        reps = reps + 1
        if reps == 1:
            interval = 1.0
        elif reps == 2:
            interval = 3.0
        else:
            interval = max(1.0, interval * 1.2)
        due = now + int(round(interval * 86_400))
    elif rating == "good":
        reps = reps + 1
        if reps == 1:
            interval = 1.0
        elif reps == 2:
            interval = 6.0
        else:
            interval = max(1.0, interval * ease)
        due = now + int(round(interval * 86_400))
    elif rating == "easy":
        ease = ease + 0.15
        reps = reps + 1
        if reps == 1:
            interval = 2.0
        elif reps == 2:
            interval = 7.0
        else:
            interval = max(1.0, interval * ease * 1.3)
        due = now + int(round(interval * 86_400))
    else:  # pragma: no cover
        raise ValueError(f"Unknown rating: {rating}")

    return CardState(
        due=due, interval_days=interval, ease_factor=ease, repetitions=reps
    )


def select_next(
    *, decks: Iterable[Deck], state: dict[str, CardState], now: int
) -> Selection:
    """Pick the next card to study, preferring due cards over new cards."""
    all_cards = [card for deck in decks for card in deck.cards]

    due_candidates: list[tuple[int, tuple[int, int], Card]] = []
    new_candidates: list[Card] = []
    future_dues: list[int] = []

    for card in all_cards:
        st = state.get(card.key)
        if st is None:
            new_candidates.append(card)
            continue

        if st.due <= now:
            due_candidates.append((st.due, card.order, card))
        else:
            future_dues.append(st.due)

    due_candidates.sort(key=lambda t: (t[0], t[1]))
    new_candidates.sort(key=lambda c: c.order)

    chosen: Card | None
    if due_candidates:
        chosen = due_candidates[0][2]
    elif new_candidates:
        chosen = new_candidates[0]
    else:
        chosen = None

    next_due = min(future_dues) if chosen is None and future_dues else None
    return Selection(
        card=chosen,
        due_count=len(due_candidates),
        new_count=len(new_candidates),
        total_count=len(all_cards),
        next_due=next_due,
    )
