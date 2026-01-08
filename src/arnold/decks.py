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


def compute_deck_id(resolved_path: Path) -> str:
    """Return a stable deck ID derived from the resolved deck path.

    This is used as a namespace prefix for state keys so two different files can
    contain identical cards without colliding.
    """
    digest = hashlib.sha1(str(resolved_path).encode("utf-8")).hexdigest()
    return digest[:12]


def _content_hashed_card_id(front: str, back: str, tags: tuple[str, ...]) -> str:
    """Return the canonical card ID: sha1 of (front, back, tags).

    `tags` must already be normalized (sorted/deduped) so tag ordering does not
    affect identity.
    """
    payload = {"back": back, "front": front, "tags": list(tags)}
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def load_deck(path: Path, *, deck_index: int) -> Deck:
    """Load and validate a deck from disk.

    Accepted formats:
    - Object format: `{ "name": "...", "cards": [...] }`
    - Array format: `[...]` (cards only)

    Notes:
    - The `id` card field is deprecated and rejected.
    - Card IDs are derived from content (`front`, `back`, `tags`).
    - Duplicate cards (same content) are deduped at load time.
    """
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
        errors.append(
            "Deck JSON must be an array of cards or an object with a 'cards' array."
        )

    if errors:
        raise DeckValidationError(path=path, errors=tuple(errors))

    if not isinstance(cards_raw, list):
        raise DeckValidationError(
            path=path,
            errors=("Top-level field 'cards' must be an array.",),
        )

    resolved_path = path.expanduser().resolve()
    deck_id = compute_deck_id(resolved_path)
    deck_name = deck_name or path.stem

    cards: list[Card] = []
    seen_ids: set[str] = set()

    for card_index, raw in enumerate(cards_raw):
        if not isinstance(raw, dict):
            errors.append(f"Card {card_index}: must be an object.")
            continue

        front = raw.get("front")
        back = raw.get("back")

        if "id" in raw:
            errors.append(
                f"Card {card_index}: field 'id' is deprecated and not allowed; remove it."
            )

        if "front" not in raw:
            errors.append(f"Card {card_index}: missing required field 'front'.")
        elif not isinstance(front, str):
            errors.append(f"Card {card_index}: field 'front' must be a string.")

        if "back" not in raw:
            errors.append(f"Card {card_index}: missing required field 'back'.")
        elif not isinstance(back, str):
            errors.append(f"Card {card_index}: field 'back' must be a string.")

        tags_raw = raw.get("tags", [])
        tags: tuple[str, ...] = ()
        if tags_raw == []:
            tags = ()
        elif isinstance(tags_raw, list) and all(isinstance(t, str) for t in tags_raw):
            tags = tuple(sorted(set(tags_raw)))
        else:
            errors.append(
                f"Card {card_index}: field 'tags' must be a list of strings when provided."
            )

        if isinstance(front, str) and isinstance(back, str):
            card_id = _content_hashed_card_id(front=front, back=back, tags=tags)
        else:
            card_id = None

        if card_id is not None and card_id in seen_ids:
            continue

        if isinstance(front, str) and isinstance(back, str) and card_id is not None:
            seen_ids.add(card_id)
            cards.append(
                Card(
                    deck_id=deck_id,
                    card_id=card_id,
                    front=front,
                    back=back,
                    tags=tags,
                    deck_name=deck_name,
                    deck_path=resolved_path,
                    order=(deck_index, card_index),
                )
            )

    if errors:
        raise DeckValidationError(path=path, errors=tuple(errors))

    return Deck(path=path, deck_id=deck_id, name=deck_name, cards=tuple(cards))


def load_decks(paths: list[Path]) -> tuple[list[Deck], list[DeckValidationError]]:
    """Load many decks, collecting per-file validation failures."""
    decks: list[Deck] = []
    failures: list[DeckValidationError] = []
    for idx, path in enumerate(paths):
        try:
            decks.append(load_deck(path, deck_index=idx))
        except DeckValidationError as e:
            failures.append(e)
    return decks, failures
