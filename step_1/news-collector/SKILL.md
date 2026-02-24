---
name: news-collector
description: Collect stock-related news into the latest JSON file under collect_info by reading config.txt parameters and running the step 1 collection script. Use when users need to refresh raw news/context inputs before summary and PDF generation.
---

# News Collector Workflow

Follow this workflow exactly.

## 1) Resolve Root And Validate Environment
- Start from current run context and walk up until `config.txt` is found.
- Treat that directory as `<root>`.
- Verify `<root>/.venv/bin/python` exists and is executable.
- If not found, stop and report:
`Shared environment missing. Initialize <root>/.venv and install requirements.txt first.`

## 2) Check Config Parameters Before Run
- Ensure `<root>/config.txt` includes and provides valid values for:
  - `COMPANY`
  - `DAY RANGE`
  - `TOPIC`
  - `TOP_K`
- If parameters are missing or malformed, stop and return script error.

## 3) Execute Step 1 Script
- Run from any directory using the shared environment:

```bash
ROOT_DIR="$PWD"
while [ "$ROOT_DIR" != "/" ] && [ ! -f "$ROOT_DIR/config.txt" ]; do
  ROOT_DIR="$(dirname "$ROOT_DIR")"
done
"$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/step_1/news-collector/scripts/collect_news.py"
```

## 4) Output Contract
- Script writes latest news JSON to:
`<root>/collect_info/<YYYY-MM-DD-HH>.json`
- Script prints:
  - `Skill root`
  - `Config`
  - `Output`
  - per-ticker write counts

## 5) Failure Handling
- If script exits non-zero, stop and return the exact error text.
- Common failure cases:
  - `config.txt` not found
  - missing shared `.venv`
  - network/request failures during feed/context fetch
