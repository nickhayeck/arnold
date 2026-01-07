import hashlib
import json
from pathlib import Path

import pytest

from arnold.decks import DeckValidationError, load_deck


def _expected_card_id(front: str, back: str, tags: list[str] | None = None) -> str:
    canonical_tags = sorted(set(tags or []))
    payload = {"back": back, "front": front, "tags": canonical_tags}
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def test_load_deck_accepts_object_format(tmp_path: Path) -> None:
    path = tmp_path / "deck.json"
    path.write_text(
        json.dumps(
            {
                "name": "Test Deck",
                "cards": [
                    {"front": "front 1", "back": "back 1", "tags": ["b", "a", "a"]},
                    {"front": "front 2", "back": "back 2"},
                ],
            }
        ),
        encoding="utf-8",
    )

    deck = load_deck(path, deck_index=0)
    assert deck.name == "Test Deck"
    assert len(deck.cards) == 2
    assert deck.cards[0].tags == ("a", "b")
    assert deck.cards[0].card_id == _expected_card_id(
        "front 1", "back 1", tags=["b", "a", "a"]
    )
    assert deck.cards[1].card_id == _expected_card_id("front 2", "back 2")

    deck_again = load_deck(path, deck_index=0)
    assert deck_again.cards[0].card_id == deck.cards[0].card_id
    assert deck_again.cards[1].card_id == deck.cards[1].card_id


def test_load_deck_accepts_array_format(tmp_path: Path) -> None:
    path = tmp_path / "deck.json"
    path.write_text(
        json.dumps(
            [
                {"front": "front a", "back": "back a"},
            ]
        ),
        encoding="utf-8",
    )

    deck = load_deck(path, deck_index=0)
    assert len(deck.cards) == 1
    assert deck.cards[0].card_id == _expected_card_id("front a", "back a")


def test_load_deck_rejects_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "deck.json"
    path.write_text("{", encoding="utf-8")

    with pytest.raises(DeckValidationError) as excinfo:
        load_deck(path, deck_index=0)

    assert "Invalid JSON" in str(excinfo.value)


def test_load_deck_rejects_missing_fields(tmp_path: Path) -> None:
    path = tmp_path / "deck.json"
    path.write_text(json.dumps([{"front": "only front"}]), encoding="utf-8")

    with pytest.raises(DeckValidationError) as excinfo:
        load_deck(path, deck_index=0)

    msg = str(excinfo.value)
    assert "missing required field 'back'" in msg


def test_load_deck_rejects_deprecated_id_field(tmp_path: Path) -> None:
    path = tmp_path / "deck.json"
    path.write_text(
        json.dumps(
            [
                {"id": "dup", "front": "front 1", "back": "back 1"},
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(DeckValidationError) as excinfo:
        load_deck(path, deck_index=0)

    assert "field 'id' is deprecated" in str(excinfo.value)


def test_load_deck_dedupes_duplicate_cards(tmp_path: Path) -> None:
    path = tmp_path / "deck.json"
    path.write_text(
        json.dumps(
            [
                {"front": "front 1", "back": "back 1", "tags": ["b", "a"]},
                {"front": "front 1", "back": "back 1", "tags": ["a", "b"]},
                {"front": "front 2", "back": "back 2"},
            ]
        ),
        encoding="utf-8",
    )

    deck = load_deck(path, deck_index=0)
    assert len(deck.cards) == 2
    assert deck.cards[0].card_id == _expected_card_id("front 1", "back 1", ["a", "b"])
    assert deck.cards[1].card_id == _expected_card_id("front 2", "back 2")


def test_load_deck_rejects_non_string_front_back(tmp_path: Path) -> None:
    path = tmp_path / "deck.json"
    path.write_text(json.dumps([{"front": 123, "back": "ok"}]), encoding="utf-8")

    with pytest.raises(DeckValidationError) as excinfo:
        load_deck(path, deck_index=0)

    assert "field 'front' must be a string" in str(excinfo.value)
