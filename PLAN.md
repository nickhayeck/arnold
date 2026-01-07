# Arnold: Achieve Total Recall — Engineering Plan

## Goals

Deliver a minimal, end-to-end study loop:
- `arnold deck1.json deck2.json ...` starts a local Flask server and opens the study UI.
- Decks are validated before serving.
- Study progress persists in a separate JSON state file (no deck mutation).

## MVP Scope

**In**
- Load one or more deck JSON files.
- Validate schema and report actionable errors.
- Study UI: show front → reveal back → rate (Again/Hard/Good/Easy) → next card.
- Minimal scheduling state per card persisted to a JSON `--state-file`.
- htmx for fragment swaps; functional without JS via normal form posts.
- Math rendering via MathJax (CDN).

**Out (explicitly)**
- Editing decks in the UI, media, cloze, add-ons.
- Sync/auth/multi-user.
- Stats dashboards, tags filtering, advanced scheduler controls.
- SQLite persistence (planned follow-on).

## Deck Format (JSON)

Canonical format (recommended):
```json
{
  "name": "Algebra",
  "cards": [
    { "id": "q1", "front": "2+2?", "back": "4", "tags": ["math"] }
  ]
}
```

Also accepted for convenience:
```json
[
  { "front": "2+2?", "back": "4" }
]
```

Card fields:
- Required: `front` (string), `back` (string)
- Optional: `id` (string|int), `tags` (list[string])

Stable IDs:
- If `id` is missing, generate a stable ID from `(resolved deck path + front + back)` using `sha1` (truncated).
- Duplicate IDs (after generation) are rejected within a deck.

Validation catches:
- Invalid JSON.
- Missing required fields.
- Duplicate IDs within a deck.
- Non-string `front`/`back` (and invalid `tags` types).

## Persistence & Data Model (State File)

Default: JSON state file (`--state-file`, default `arnold_state.json`).
- Deck files are never mutated.
- Writes are atomic-ish: write a temp file then `replace`.

State is keyed by a stable card key including deck identity:
- `card_key = "<deck_id>:<card_id>"`
- `deck_id` is derived from the resolved absolute deck path.

Per-card scheduling fields (MVP):
- `due` (unix seconds)
- `interval_days` (float)
- `ease_factor` (float)
- `repetitions` (int)

## Scheduling (MVP)

Use a small SM-2-like update with four ratings:
- Again / Hard / Good / Easy

Rules of thumb:
- Due cards first; if none due, show new cards (no state yet).
- Deterministic updates (inject `now()` for tests).

## CLI Interface

Command:
- `arnold <deck.json> [<deck2.json> ...]`

Flags (MVP):
- `--state-file PATH` (default `arnold_state.json`)
- `--host TEXT` (default `127.0.0.1`)
- `--port INT` (default `8000`)
- `--no-browser` (don’t open browser)
- `--validate-only` (validate decks and exit 0/1 with messages)
- `--debug` (Flask debug mode)

Behavior:
- Always validate decks before starting.
- Print the URL to stdout.
- Open the browser by default unless `--no-browser`.

## Web Routes & UI Flow

Routes:
- `GET /`: show the next card (front). Includes a status line (decks/cards loaded, due/new counts).
- `POST /reveal`: reveal the back for a specific card.
- `POST /rate`: apply rating, persist state, then advance to the next card.

htmx interactions:
- Forms include `hx-post` targeting a swappable `#study-pane` fragment.
- When requested by htmx, routes return only the `#study-pane` fragment; otherwise return full pages/redirects.

No-cards state:
- If nothing is due and there are no new cards, show a “no cards available” message and the next due time (if known).

## Math / LaTeX Rendering

MathJax is included via CDN in the base template.
Use standard MathJax delimiters inside JSON strings:
- Inline: `\\( a^2 + b^2 = c^2 \\)`
- Display: `$$\\int_0^1 x^2 dx$$`

Note: JSON strings require escaping backslashes.

## Testing Strategy (pytest)

Unit tests only for MVP:
- Deck validation: invalid JSON, missing fields, type errors, duplicate IDs.
- State I/O: save/load and temp-then-replace behavior.
- Scheduler: deterministic rating updates with a fixed `now`.
- Selection: due cards prioritized over new cards.

No browser automation tests for MVP.

## Follow-on Milestones

1) Import/export helpers and schema docs in README.
2) Deck listing page + per-deck filtering and tags.
3) Basic stats page (streak, due counts over time).
4) Scheduler improvements (learning steps, leech, bury/suspend).
5) “Reset progress” and “forget card” actions.
6) Optional SQLite backend (same model, different persistence).

## PR Notes (living)

Done (MVP):
- Typer CLI: `arnold <decks...>` with `--state-file/--host/--port/--no-browser/--validate-only/--debug`.
- Deck loader + validation with stable ID generation and clear error messages.
- JSON state store (temp write + replace) keyed by `<deck_id>:<card_id>`.
- Minimal SM-2-like scheduler with Again/Hard/Good/Easy and due/new selection.
- Flask + Jinja2 UI with htmx swaps, progressive form posts, Pico.css + MathJax via CDN.
- pytest unit tests for decks/state/scheduler selection.

Next:
- Add a small “decks/status” page and basic tag filtering.
- Add “reset progress” and “forget card” actions.
- Improve scheduler (learning steps, per-rating intervals, bury/suspend).
- Add basic stats (daily reviews, due histogram).
- Offer optional SQLite persistence (same models, different storage).
