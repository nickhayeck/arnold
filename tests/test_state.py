import json
from pathlib import Path

import pytest

from arnold.models import CardState
from arnold.state import StateFileError, StateStore


def test_state_store_save_and_load_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    store = StateStore.load(path)
    assert store.cards == {}

    store.set(
        "deck:card",
        CardState(due=123, interval_days=1.0, ease_factor=2.5, repetitions=1),
    )
    store.save(now=999)

    assert path.exists()
    assert not (tmp_path / "state.json.tmp").exists()

    store2 = StateStore.load(path)
    assert store2.get("deck:card") == CardState(
        due=123, interval_days=1.0, ease_factor=2.5, repetitions=1
    )


def test_state_store_rejects_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text("{", encoding="utf-8")

    with pytest.raises(StateFileError) as excinfo:
        StateStore.load(path)

    assert "Invalid JSON" in str(excinfo.value)


def test_state_store_accepts_legacy_flat_mapping(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text(
        json.dumps(
            {
                "deck:card": {
                    "due": 1,
                    "interval_days": 0,
                    "ease_factor": 2.5,
                    "repetitions": 0,
                }
            }
        ),
        encoding="utf-8",
    )

    store = StateStore.load(path)
    assert store.get("deck:card") == CardState(
        due=1, interval_days=0.0, ease_factor=2.5, repetitions=0
    )
