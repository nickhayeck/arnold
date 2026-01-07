from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Rating = Literal["again", "hard", "good", "easy"]


@dataclass(frozen=True, slots=True)
class Card:
    deck_id: str
    card_id: str
    front: str
    back: str
    tags: tuple[str, ...]
    deck_name: str
    deck_path: Path
    order: tuple[int, int]

    @property
    def key(self) -> str:
        return f"{self.deck_id}:{self.card_id}"


@dataclass(frozen=True, slots=True)
class Deck:
    path: Path
    deck_id: str
    name: str
    cards: tuple[Card, ...]


@dataclass(slots=True)
class CardState:
    due: int
    interval_days: float
    ease_factor: float
    repetitions: int

    def to_json(self) -> dict[str, object]:
        return {
            "due": self.due,
            "interval_days": self.interval_days,
            "ease_factor": self.ease_factor,
            "repetitions": self.repetitions,
        }

    @classmethod
    def from_json(cls, data: object) -> CardState:
        if not isinstance(data, dict):
            raise TypeError("card state must be an object")

        due = data.get("due")
        interval_days = data.get("interval_days")
        ease_factor = data.get("ease_factor")
        repetitions = data.get("repetitions")

        if not isinstance(due, int):
            raise TypeError("card state field 'due' must be an int unix timestamp")
        if not isinstance(interval_days, (int, float)):
            raise TypeError("card state field 'interval_days' must be a number")
        if not isinstance(ease_factor, (int, float)):
            raise TypeError("card state field 'ease_factor' must be a number")
        if not isinstance(repetitions, int):
            raise TypeError("card state field 'repetitions' must be an int")

        return cls(
            due=due,
            interval_days=float(interval_days),
            ease_factor=float(ease_factor),
            repetitions=repetitions,
        )


@dataclass(frozen=True, slots=True)
class Selection:
    card: Card | None
    due_count: int
    new_count: int
    total_count: int
    next_due: int | None

