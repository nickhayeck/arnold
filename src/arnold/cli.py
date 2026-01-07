from __future__ import annotations

import webbrowser
from pathlib import Path

import typer

from arnold.decks import load_decks
from arnold.state import StateFileError, StateStore
from arnold.web import create_app


def main(
    decks: list[Path] = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        readable=True,
        help="Deck JSON file(s) to study.",
    ),
    state_file: Path = typer.Option(
        Path("arnold_state.json"),
        "--state-file",
        help="Path to the JSON state file (progress is stored here).",
    ),
    host: str = typer.Option("127.0.0.1", "--host", help="Host interface to bind."),
    port: int = typer.Option(8000, "--port", help="Port to listen on."),
    no_browser: bool = typer.Option(
        False,
        "--no-browser",
        "--no-open",
        help="Do not open a browser automatically.",
    ),
    validate_only: bool = typer.Option(
        False,
        "--validate-only",
        "--validate",
        help="Validate deck files and exit (no server).",
    ),
    debug: bool = typer.Option(False, "--debug", help="Enable Flask debug mode."),
) -> None:
    decks = [p.expanduser() for p in decks]
    state_file = state_file.expanduser()

    loaded_decks, failures = load_decks(decks)
    if failures:
        for failure in failures:
            typer.echo(str(failure), err=True)
            typer.echo("", err=True)
        raise typer.Exit(code=1)

    if validate_only:
        typer.echo(f"Validated {len(loaded_decks)} deck(s).")
        raise typer.Exit(code=0)

    try:
        state_store = StateStore.load(state_file)
    except StateFileError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1)

    flask_app = create_app(decks=loaded_decks, state_store=state_store)

    url = f"http://{host}:{port}/"
    typer.echo(url)

    if not no_browser:
        webbrowser.open(url)

    flask_app.run(host=host, port=port, debug=debug, use_reloader=False)


def entrypoint() -> None:
    typer.run(main)
