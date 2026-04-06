#!/usr/bin/env python3
"""Run the evaluation pipeline once: URL → download → extract → (optional) LLM JSON."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Allow `python scripts/run_pipeline.py` from repo root
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config.concurrency import init_concurrency
from pipeline.orchestrator import run_pipeline


async def _async_main() -> int:
    parser = argparse.ArgumentParser(description="Run URL → pipeline → JSON")
    parser.add_argument("--url", required=True, help="File URL (OneDrive, Google Docs, or direct)")
    parser.add_argument(
        "--file-path",
        default=None,
        help='CSV-style path e.g. "ПКС2025/Астана/Иванов/Группа1/план.docx"',
    )
    parser.add_argument(
        "--extract-only",
        action="store_true",
        help="Skip LLM; print extraction + rubric preview only",
    )
    args = parser.parse_args()

    init_concurrency()
    result = await run_pipeline(args.url, args.file_path, extract_only=args.extract_only)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_async_main()))


if __name__ == "__main__":
    main()
