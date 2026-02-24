#!/usr/bin/env python3
"""Write formatted summary output for stock-report-writer step 6."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)


def normalize_summary(text: Any) -> str:
    if not isinstance(text, str):
        return ""
    out = text.strip()
    if out.startswith("Summary:"):
        out = out[len("Summary:") :].strip()
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Write output TXT from sections payload.")
    parser.add_argument("--payload", required=True, help="Path to JSON payload file.")
    args = parser.parse_args()

    payload_path = Path(args.payload)
    if not payload_path.is_file():
        fail(f"Payload file not found: {payload_path}")

    try:
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"Invalid payload JSON: {exc}")

    if not isinstance(payload, dict):
        fail("Payload root must be an object")

    output_txt_path = payload.get("output_txt_path")
    sections = payload.get("sections")
    if not isinstance(output_txt_path, str) or not output_txt_path.strip():
        fail("Payload missing required string field: output_txt_path")
    if not isinstance(sections, list):
        fail("Payload missing required list field: sections")

    lines: list[str] = []
    for idx, section in enumerate(sections, start=1):
        if not isinstance(section, dict):
            fail(f"Section {idx} must be an object")
        field = section.get("field")
        if not isinstance(field, str) or not field.strip():
            fail(f"Section {idx} missing required string field: field")
        summary = normalize_summary(section.get("summary"))
        if not summary:
            fail(f"Section {idx} missing required non-empty field: summary")

        lines.append(f"=== {field.strip()} ===")
        lines.append(f"Summary: {summary}")
        lines.append("")

    content = "\n".join(lines).rstrip() + "\n"
    target = Path(output_txt_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    print(str(target))


if __name__ == "__main__":
    main()
