from pathlib import Path

from arnold.models import Card, CardState, Deck
from arnold.scheduler import apply_rating, select_next


def test_apply_rating_good_from_new_is_one_day() -> None:
    now = 1_700_000_000
    st = apply_rating(existing=None, rating="good", now=now)
    assert st.repetitions == 1
    assert st.interval_days == 1.0
    assert st.due == now + 86_400


def test_apply_rating_again_resets_and_is_soon() -> None:
    now = 1_700_000_000
    prev = CardState(due=now, interval_days=10.0, ease_factor=2.5, repetitions=5)
    st = apply_rating(existing=prev, rating="again", now=now)
    assert st.repetitions == 0
    assert st.interval_days == 0.0
    assert st.due == now + 60


def test_select_next_prefers_due_over_new(tmp_path: Path) -> None:
    deck_path = tmp_path / "deck.json"
    cards = (
        Card(
            deck_id="d",
            card_id="1",
            front="f1",
            back="b1",
            tags=(),
            deck_name="D",
            deck_path=deck_path,
            order=(0, 0),
        ),
        Card(
            deck_id="d",
            card_id="2",
            front="f2",
            back="b2",
            tags=(),
            deck_name="D",
            deck_path=deck_path,
            order=(0, 1),
        ),
    )
    deck = Deck(path=deck_path, deck_id="d", name="D", cards=cards)

    now = 100
    state = {
        cards[1].key: CardState(
            due=0, interval_days=1.0, ease_factor=2.5, repetitions=1
        )
    }
    sel = select_next(decks=[deck], state=state, now=now)
    assert sel.card == cards[1]
    assert sel.due_count == 1
    assert sel.new_count == 1


def test_select_next_returns_none_when_all_future(tmp_path: Path) -> None:
    deck_path = tmp_path / "deck.json"
    card = Card(
        deck_id="d",
        card_id="1",
        front="f1",
        back="b1",
        tags=(),
        deck_name="D",
        deck_path=deck_path,
        order=(0, 0),
    )
    deck = Deck(path=deck_path, deck_id="d", name="D", cards=(card,))

    now = 100
    state = {
        card.key: CardState(due=200, interval_days=1.0, ease_factor=2.5, repetitions=1)
    }
    sel = select_next(decks=[deck], state=state, now=now)
    assert sel.card is None
    assert sel.next_due == 200
