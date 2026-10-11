"""Command: import data/registered/ into MongoDB (idempotent, additive-only).

Usage (from the backend/ directory):
    ..\\.venv\\Scripts\\python.exe -m app.import_command [--root PATH]

Reads the ORIGINAL dataset read-only; upserts registered_persons +
registered_images; never touches users, missing_persons, or history.
"""
import argparse
import asyncio
import json
import sys

from .config import settings
from .db import ensure_indexes, get_client
from .services.dataset_import import import_registered_dataset


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Import data/registered/ into MongoDB")
    parser.add_argument("--root", default=None, help="Dataset root (defaults to MPP_ORIGINAL_ROOT/data/registered)")
    args = parser.parse_args(argv)

    async def _run():
        await ensure_indexes()
        db = get_client()[settings.mongodb_db]
        return await import_registered_dataset(db, args.root)

    report = asyncio.run(_run())
    print(json.dumps(report, indent=2, default=str))
    return 0 if not report.get("errors") else 2


if __name__ == "__main__":
    sys.exit(main())
