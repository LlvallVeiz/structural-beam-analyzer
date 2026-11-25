"""Module entry point: ``python -m beam_analyzer <command> ...``."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
