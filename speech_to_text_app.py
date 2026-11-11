"""Deprecated compatibility entrypoint for Saydraft.

New code should run ``python -m saydraft`` or import ``saydraft.main``.
"""

from saydraft.main import main


if __name__ == "__main__":
    raise SystemExit(main())
