from __future__ import annotations

from pathlib import Path

from arnold.models import Card, Deck
from arnold.state import StateStore
from arnold.web import create_app


def _make_app(tmp_path: Path):
    deck_path = tmp_path / "deck.json"
    card = Card(
        deck_id="d",
        card_id="c1",
        front="front",
        back="back",
        tags=(),
        deck_name="Deck",
        deck_path=deck_path,
        order=(0, 0),
    )
    deck = Deck(path=deck_path, deck_id="d", name="Deck", cards=(card,))
    store = StateStore.load(tmp_path / "state.json")
    app = create_app(decks=[deck], state_store=store, now_fn=lambda: 1000)
    app.testing = True
    return app, card, store


def test_hotkeys_render_and_history_undo_flow(tmp_path: Path) -> None:
    app, card, store = _make_app(tmp_path)
    client = app.test_client()

    resp = client.get("/")
    assert resp.status_code == 200
    assert b'data-hotkey="space"' in resp.data

    headers = {"HX-Request": "true"}

    resp = client.post("/reveal", data={"card_key": card.key}, headers=headers)
    assert resp.status_code == 200
    assert b'data-hotkey="1"' in resp.data
    assert b'data-hotkey="2"' in resp.data
    assert b'data-hotkey="3"' in resp.data
    assert b'data-hotkey="4"' in resp.data

    resp = client.post(
        "/rate",
        data={"card_key": card.key, "rating": "good"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert b"Done 1" in resp.data
    assert card.key in store.cards

    resp = client.post("/history/back", headers=headers)
    assert resp.status_code == 200
    assert b"History" in resp.data
    assert b"Next" in resp.data
    assert b"Oops" not in resp.data

    resp = client.post("/history/next", headers=headers)
    assert resp.status_code == 200
    assert b"No cards available" in resp.data

    resp = client.post("/undo", headers=headers)
    assert resp.status_code == 200
    assert b"Done 0" in resp.data
    assert b"Oops" in resp.data
    assert card.key not in store.cards

