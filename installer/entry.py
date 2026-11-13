"""Frozen entrypoint; package verification never starts application services."""

import sys

from saydraft.main import main
from saydraft.package_check import main as check_package


if __name__ == "__main__":
    if sys.argv[1:2] == ["--verify-package"]:
        raise SystemExit(check_package(sys.argv[2:]))
    raise SystemExit(main())
