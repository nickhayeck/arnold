from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from arnold.models import CardState


@dataclass(frozen=True, slots=True)
class StateFileError(Exception):
    path: Path
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


@dataclass(slots=True)
class StateStore:
    path: Path
    cards: dict[str, CardState] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> StateStore:
        store = cls(path=path)
        store._load_from_disk()
        return store

    def _load_from_disk(self) -> None:
        if not self.path.exists():
            self.cards = {}
            return

        try:
            text = self.path.read_text(encoding="utf-8")
        except OSError as e:
            raise StateFileError(path=self.path, message=f"Could not read state file: {e}")

        try:
            raw = json.loads(text) if text.strip() else {}
        except json.JSONDecodeError as e:
            msg = f"Invalid JSON: {e.msg} (line {e.lineno}, col {e.colno})"
            raise StateFileError(path=self.path, message=msg)

        cards_obj: Any
        if isinstance(raw, dict) and isinstance(raw.get("cards"), dict):
            cards_obj = raw["cards"]
        elif isinstance(raw, dict):
            cards_obj = raw
        else:
            raise StateFileError(path=self.path, message="State file must be a JSON object.")

        parsed: dict[str, CardState] = {}
        for key, value in cards_obj.items():
            if not isinstance(key, str):
                raise StateFileError(path=self.path, message="State keys must be strings.")
            try:
                parsed[key] = CardState.from_json(value)
            except Exception as e:  # noqa: BLE001
                raise StateFileError(path=self.path, message=f"Invalid state for '{key}': {e}")

        self.cards = parsed

    def get(self, key: str) -> CardState | None:
        return self.cards.get(key)

    def set(self, key: str, state: CardState) -> None:
        self.cards[key] = state

    def save(self, *, now: int) -> None:
        payload = {
            "version": 1,
            "updated_at": now,
            "cards": {k: v.to_json() for k, v in sorted(self.cards.items())},
        }

        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_name(self.path.name + ".tmp")

        try:
            with tmp_path.open("w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, sort_keys=True)
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self.path)
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
