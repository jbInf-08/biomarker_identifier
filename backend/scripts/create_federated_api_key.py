"""
One-off CLI: insert a ServiceApiKey row using the same hashing as app.api.deps.

Run from the backend directory with DATABASE_URL and SECRET_KEY set, e.g.:

  python scripts/create_federated_api_key.py --name "edge-node-1" --scope federated:write
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a federated/service API key")
    parser.add_argument("--name", required=True, help="Human-readable key name")
    parser.add_argument(
        "--scope",
        action="append",
        dest="scopes",
        default=None,
        help="Optional scope (repeat for multiple)",
    )
    args = parser.parse_args()

    async def _run() -> None:
        from app.api.deps import create_service_api_key
        from app.core.database import get_db_context, init_db

        await init_db()
        scopes = args.scopes if args.scopes is not None else []
        with get_db_context() as db:
            row, raw = create_service_api_key(db, name=args.name, scopes=scopes)
            key_id, key_prefix = row.id, row.key_prefix
        print(f"id={key_id}")
        print(f"key_prefix={key_prefix}")
        print("api_key (save once):")
        print(raw)

    asyncio.run(_run())


if __name__ == "__main__":
    main()
