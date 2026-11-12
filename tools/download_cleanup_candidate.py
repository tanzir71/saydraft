"""Explicit developer-only candidate transfer; no default or implicit download."""

import argparse
import json
from pathlib import Path

from saydraft.cleanup.llm.candidates import DEFAULT_CATALOG, download_candidate, load_candidates


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--candidate")
    parser.add_argument("--directory", type=Path)
    args = parser.parse_args(argv)
    if args.list:
        for model in load_candidates(args.catalog)["models"]:
            print(json.dumps({"id": model["id"], "label": model["label"], "license": model["license"],
                              "bytes": sum(file["size"] for file in model["files"]), "status": model["status"]}))
        return 0
    if not args.candidate or args.directory is None:
        parser.error("choose --list, or explicitly provide --candidate and --directory")
    last = -1

    def progress(value):
        nonlocal last
        if value // 10 != last:
            last = value // 10
            print(json.dumps({"candidate": args.candidate, "percent": value}), flush=True)

    result = download_candidate(args.candidate, args.directory, catalog=args.catalog, progress_callback=progress)
    print(json.dumps({"candidate": args.candidate, "verified": True, "directory": str(result)}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
