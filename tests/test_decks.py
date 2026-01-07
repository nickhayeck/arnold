import json
from pathlib import Path

import pytest

from arnold.decks import DeckValidationError, load_deck


def test_load_deck_accepts_object_format(tmp_path: Path) -> None:
    path = tmp_path / "deck.json"
    path.write_text(
        json.dumps(
            {
                "name": "Test Deck",
                "cards": [
                    {"id": 1, "front": "front 1", "back": "back 1"},
                    {"front": "front 2", "back": "back 2"},
                ],
            }
        ),
        encoding="utf-8",
    )

    deck = load_deck(path, deck_index=0)
    assert deck.name == "Test Deck"
    assert len(deck.cards) == 2
    assert deck.cards[0].card_id == "1"
    assert deck.cards[1].card_id

    deck_again = load_deck(path, deck_index=0)
    assert deck_again.cards[1].card_id == deck.cards[1].card_id


def test_load_deck_accepts_array_format(tmp_path: Path) -> None:
    path = tmp_path / "deck.json"
    path.write_text(
        json.dumps(
            [
                {"id": "a", "front": "front a", "back": "back a"},
            ]
        ),
        encoding="utf-8",
    )

    deck = load_deck(path, deck_index=0)
    assert len(deck.cards) == 1
    assert deck.cards[0].card_id == "a"


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


def test_load_deck_rejects_duplicate_ids(tmp_path: Path) -> None:
    path = tmp_path / "deck.json"
    path.write_text(
        json.dumps(
            [
                {"id": "dup", "front": "front 1", "back": "back 1"},
                {"id": "dup", "front": "front 2", "back": "back 2"},
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(DeckValidationError) as excinfo:
        load_deck(path, deck_index=0)

    assert "duplicate id 'dup'" in str(excinfo.value)


def test_load_deck_rejects_non_string_front_back(tmp_path: Path) -> None:
    path = tmp_path / "deck.json"
    path.write_text(json.dumps([{"front": 123, "back": "ok"}]), encoding="utf-8")

    with pytest.raises(DeckValidationError) as excinfo:
        load_deck(path, deck_index=0)

    assert "field 'front' must be a string" in str(excinfo.value)

