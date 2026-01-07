# Arnold: Achieve Total Recall — Agent Notes

This repo is a lightweight, local-first, Anki-like study tool:
- Python-first (stdlib where possible)
- Flask + Jinja2 for the web UI
- Typer for the CLI
- pytest for tests
- htmx via CDN (no npm/build tooling)

## Quickstart

Run the app (opens a browser by default):
- `arnold examples/basic_deck.json`
- `arnold --host 127.0.0.1 --port 8000 examples/basic_deck.json`
- If the console script isn’t on your PATH yet: `python -m arnold examples/basic_deck.json`

Validate decks without starting the server:
- `arnold --validate-only examples/basic_deck.json`

Use a specific state file:
- `arnold --state-file arnold_state.json examples/basic_deck.json`

Disable opening the browser:
- `arnold --no-browser examples/basic_deck.json`

## Tests

Run unit tests:
- `pytest`
- If `pytest` isn’t on PATH: `python -m pytest`
- Dev install (recommended): `pip install -e ".[dev]"`

Guardrails for tests:
- Deterministic: inject time (`now`) rather than using real clock.
- No network calls.
- Prefer unit tests over browser/UI tests for MVP.

## Repo Structure

- `src/arnold/cli.py`: Typer CLI entrypoint (`arnold ...`)
- `src/arnold/web.py`: Flask app factory + routes
- `src/arnold/decks.py`: Deck loading + validation + stable ID generation
- `src/arnold/state.py`: JSON state read/write (atomic-ish saves)
- `src/arnold/scheduler.py`: Scheduling updates + next-card selection
- `src/arnold/models.py`: Small dataclasses used across modules
- `src/arnold/templates/`: Jinja templates (htmx-enhanced, no build tooling)
- `tests/`: pytest unit tests

## Coding Conventions

- Stdlib-first (json/pathlib/datetime/hashlib/tempfile/etc.).
- Keep functions small and testable; prefer pure functions.
- Type hints where reasonable; use dataclasses for simple data.
- Minimal dependencies: only add packages when clearly justified.
- Keep frontend minimal: Jinja templates + CDN scripts/styles only.

## Operational Guardrails

- Do not mutate deck JSON files; progress lives in the state file.
- State writes should be atomic-ish (temp write then replace).
- Avoid hidden global state; prefer app factory + dependency injection.
- No network access in tests; no build tooling for frontend.

## Release Workflow

1. Bump versions in:
   - `pyproject.toml`
   - `src/arnold/__init__.py`
   - `uv.lock` (editable package version)
2. Update docs/examples as needed.
3. Validate locally:
   - `.venv/bin/python -m pytest`
   - `.venv/bin/python -m ruff check .`
4. Release:
   - `git add -A && git commit -m "Release vX.Y.Z"`
   - `git push`
   - `git tag -a vX.Y.Z -m "Release vX.Y.Z: <summary>"`
   - `git push origin vX.Y.Z`
