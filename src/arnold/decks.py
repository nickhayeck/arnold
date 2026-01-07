from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from arnold.models import Card, Deck


@dataclass(frozen=True, slots=True)
class DeckValidationError(Exception):
    path: Path
    errors: tuple[str, ...]

    def __str__(self) -> str:
        lines = [f"{self.path}:"]
        lines.extend(f"- {e}" for e in self.errors)
        return "\n".join(lines)


def compute_deck_id(path: Path) -> str:
    resolved = path.expanduser().resolve()
    digest = hashlib.sha1(str(resolved).encode("utf-8")).hexdigest()
    return digest[:12]


def _generated_card_id(deck_id: str, front: str, back: str) -> str:
    raw = f"{deck_id}\n{front}\n{back}".encode("utf-8")
    digest = hashlib.sha1(raw).hexdigest()
    return digest[:12]


def load_deck(path: Path, *, deck_index: int) -> Deck:
    errors: list[str] = []

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise DeckValidationError(path=path, errors=(f"Could not read file: {e}",))

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        msg = f"Invalid JSON: {e.msg} (line {e.lineno}, col {e.colno})"
        raise DeckValidationError(path=path, errors=(msg,))

    deck_name: str | None = None
    cards_raw: Any = None

    if isinstance(data, list):
        cards_raw = data
    elif isinstance(data, dict):
        if isinstance(data.get("name"), str):
            deck_name = data["name"]
        cards_raw = data.get("cards")
        if cards_raw is None:
            errors.append("Missing required top-level field 'cards' (array).")
    else:
        errors.append("Deck JSON must be an array of cards or an object with a 'cards' array.")

    if errors:
        raise DeckValidationError(path=path, errors=tuple(errors))

    if not isinstance(cards_raw, list):
        raise DeckValidationError(
            path=path,
            errors=("Top-level field 'cards' must be an array.",),
        )

    deck_id = compute_deck_id(path)
    deck_name = deck_name or path.stem

    cards: list[Card] = []
    seen_ids: dict[str, int] = {}

    for card_index, raw in enumerate(cards_raw):
        if not isinstance(raw, dict):
            errors.append(f"Card {card_index}: must be an object.")
            continue

        front = raw.get("front")
        back = raw.get("back")

        if "front" not in raw:
            errors.append(f"Card {card_index}: missing required field 'front'.")
        elif not isinstance(front, str):
            errors.append(f"Card {card_index}: field 'front' must be a string.")

        if "back" not in raw:
            errors.append(f"Card {card_index}: missing required field 'back'.")
        elif not isinstance(back, str):
            errors.append(f"Card {card_index}: field 'back' must be a string.")

        raw_id = raw.get("id")
        card_id: str | None
        if raw_id is None:
            if isinstance(front, str) and isinstance(back, str):
                card_id = _generated_card_id(deck_id, front, back)
            else:
                card_id = None
        elif isinstance(raw_id, (str, int)):
            card_id = str(raw_id)
        else:
            card_id = None
            errors.append(f"Card {card_index}: field 'id' must be a string or int when provided.")

        tags_raw = raw.get("tags", [])
        tags: tuple[str, ...] = ()
        if tags_raw == []:
            tags = ()
        elif isinstance(tags_raw, list) and all(isinstance(t, str) for t in tags_raw):
            tags = tuple(tags_raw)
        else:
            errors.append(f"Card {card_index}: field 'tags' must be a list of strings when provided.")

        if card_id is not None:
            first_seen = seen_ids.get(card_id)
            if first_seen is not None:
                errors.append(
                    f"Card {card_index}: duplicate id '{card_id}' (already used by card {first_seen})."
                )
            else:
                seen_ids[card_id] = card_index

        if isinstance(front, str) and isinstance(back, str) and card_id is not None:
            cards.append(
                Card(
                    deck_id=deck_id,
                    card_id=card_id,
                    front=front,
                    back=back,
                    tags=tags,
                    deck_name=deck_name,
                    deck_path=path.expanduser().resolve(),
                    order=(deck_index, card_index),
                )
            )

    if errors:
        raise DeckValidationError(path=path, errors=tuple(errors))

    return Deck(path=path, deck_id=deck_id, name=deck_name, cards=tuple(cards))


def load_decks(paths: list[Path]) -> tuple[list[Deck], list[DeckValidationError]]:
    decks: list[Deck] = []
    failures: list[DeckValidationError] = []
    for idx, path in enumerate(paths):
        try:
            decks.append(load_deck(path, deck_index=idx))
        except DeckValidationError as e:
            failures.append(e)
    return decks, failures

