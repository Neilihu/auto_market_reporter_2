#!/usr/bin/env python3
"""Prepare structured input for stock-report-writer step 2/3/4."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


def fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)


def find_root_from(start: Path) -> Path:
    cur = start.resolve()
    for candidate in [cur, *cur.parents]:
        if (candidate / "config.txt").is_file():
            return candidate
    fail("config.txt not found while walking up from current directory")


def parse_config_sections(config_path: Path) -> dict[str, str]:
    section_re = re.compile(r"^([A-Z0-9_ ]+):\s*(.*)$")
    data: dict[str, list[str]] = {}
    key: str | None = None

    for raw in config_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        m = section_re.match(line)
        if m:
            key = m.group(1).strip()
            data.setdefault(key, [])
            rest = m.group(2).strip()
            if rest:
                data[key].append(rest)
            continue

        if key is not None:
            data[key].append(line)

    return {k: "\n".join(v).strip() for k, v in data.items()}


def parse_summary_length(raw: str | None) -> tuple[int, int]:
    default = (200, 300)
    if not raw:
        return default
    m = re.search(r"(\d+)\s*-\s*(\d+)", raw)
    if not m:
        return default
    low = int(m.group(1))
    high = int(m.group(2))
    if low <= 0 or high <= 0:
        return default
    if low > high:
        low, high = high, low
    return (low, high)


def parse_model(raw: str | None) -> str:
    if not raw:
        return "gpt-5-mini"
    model = raw.strip().splitlines()[0].strip()
    return model or "gpt-5-mini"


def newest_json_path(collect_dir: Path) -> Path:
    json_files = sorted(collect_dir.glob("*.json"), key=lambda p: (p.stat().st_mtime, p.name))
    if not json_files:
        fail("No JSON files found in collect_info")
    return json_files[-1]


def extract_contexts(field_payload: Any) -> list[str]:
    if not isinstance(field_payload, list):
        return []
    contexts: list[str] = []
    for item in field_payload:
        if not isinstance(item, dict):
            continue
        ctx = item.get("context")
        if isinstance(ctx, str):
            text = ctx.strip()
            if text:
                contexts.append(text)
    return contexts


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare data for stock summary generation.")
    parser.add_argument("--cwd", default=".", help="Starting directory to resolve project root.")
    args = parser.parse_args()

    root = find_root_from(Path(args.cwd))
    config_path = root / "config.txt"
    collect_dir = root / "collect_info"

    if not collect_dir.is_dir():
        fail("collect_info directory not found")

    cfg = parse_config_sections(config_path)
    min_words, max_words = parse_summary_length(cfg.get("SUMMARY LENGTH"))
    model = parse_model(cfg.get("MODEL"))

    input_json_path = newest_json_path(collect_dir)
    try:
        payload = json.loads(input_json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"Invalid JSON in input file: {exc}")

    if not isinstance(payload, dict):
        fail("Input JSON root must be an object")

    results = payload.get("results")
    if not isinstance(results, dict):
        fail("Input JSON missing required object field: results")

    topic = payload.get("topic")
    if isinstance(topic, list):
        topic_terms = [x.strip() for x in topic if isinstance(x, str) and x.strip()]
    else:
        topic_terms = []

    fields = [{"name": str(name), "contexts": extract_contexts(data)} for name, data in results.items()]

    output = {
        "root": str(root),
        "input_json_path": str(input_json_path),
        "output_txt_path": str(collect_dir / f"{input_json_path.stem}.txt"),
        "model": model,
        "min_words": min_words,
        "max_words": max_words,
        "topic": topic_terms,
        "fields": fields,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
