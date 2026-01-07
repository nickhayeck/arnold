# Arnold: Achieve Total Recall
Wouldn't it be nice if Arnold Schwarzenegger had a command-line application that allowed him to quickly study any topic? If he were born just 78 years later, he could've used `arnold`.

## Why?
I found Anki too heavyweight, has a bad UI, doesn't natively support json, and isn't built for version control. This is a simpler application designed to remedy those faults.

## Install

Arnold is not published to PyPI (yet). For now, install from GitHub Releases artifacts:
1. Download the latest `arnold-<version>-py3-none-any.whl` from the Releases page.
2. Install it with either:
   - `pipx install ./arnold-<version>-py3-none-any.whl`
   - `pip install ./arnold-<version>-py3-none-any.whl`

## Quickstart

Run the app (opens a browser by default):
```bash
arnold examples/basic_deck.json
```

If you haven't installed the console script yet:
```bash
PYTHONPATH=src python -m arnold examples/basic_deck.json
```

Validate decks only (no server):
```bash
arnold --validate-only examples/basic_deck.json
```

Choose a state file (progress is saved here, it is in `arnold_state.json` by default):
```bash
arnold --state-file arnold_state.json examples/basic_deck.json
```

Common flags:
- `--host 127.0.0.1` / `--port 8000`
- `--no-browser`
- `--debug`

## Deck JSON Format

Canonical format:
```json
{
  "name": "Algebra",
  "cards": [
    { "id": "q1", "front": "2+2?", "back": "4", "tags": ["math"] }
  ]
}
```

Also accepted:
```json
[
  { "front": "2+2?", "back": "4" }
]
```

Card fields:
- Required: `front` (string), `back` (string)
- Optional: `id` (string|int), `tags` (list of strings)

If `id` is omitted, Arnold generates a stable ID from `(resolved deck path + front + back)`.

## Math / LaTeX

MathJax is enabled in the UI. Use standard delimiters in your card text:
- Inline: `\\( a^2 + b^2 = c^2 \\)`
- Display: `$$\\int_0^1 x^2 dx$$`

Note: JSON strings require escaping backslashes.

## State File

By default, progress is stored in `arnold_state.json` (configurable with `--state-file`).
Writes are atomic-ish (temp file + replace) to reduce corruption risk.

## UI Notes

- System theme (light/dark) is respected.
- Top bar shows: `Due`, `New`, and `Done` (done is per-session, resets when the server restarts).
- Rating buttons are: `Oops / Hard / Medium / Easy`, with a small preview of how long the card will sleep.

## Development

Install in editable mode with dev dependencies:
```bash
pip install -e ".[dev]"
```

Run tests:
```bash
python -m pytest
```

Run lint:
```bash
python -m ruff check .
```
