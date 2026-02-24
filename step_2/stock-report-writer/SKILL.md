---
name: stock-report-writer
description: Generate field-by-field English stock report summaries from the latest JSON in collect_info and write a same-name TXT file. Use when users want per-field stock context summaries with word range control from config.txt SUMMARY LENGTH and model selection from config.txt MODEL, with no global intro section.
---

# Stock Report Writer Workflow

Follow this workflow exactly.

## 1) LLM Orchestration
- Start in the user's current directory and treat it as run context.
- Execute script A for steps 2/3/4, run LLM step 5, then execute script B for step 6.
- If any script returns non-zero, stop and return the error text.

## 2-4) Execute Script A (prepare inputs)
- Script path: `scripts/prepare_inputs.py`
- Run from skill directory; pass the original run directory through `--cwd`.
- Before running scripts, verify `<root>/.venv/bin/python` exists. If missing, stop and report:
`Shared environment missing. Initialize <root>/.venv and install requirements.txt first.`

```bash
ORIG_CWD="$PWD"
if [ -d "$PWD/step_2/stock-report-writer" ]; then
  cd "$PWD/step_2/stock-report-writer"
fi
ROOT_DIR="$ORIG_CWD"
while [ "$ROOT_DIR" != "/" ] && [ ! -f "$ROOT_DIR/config.txt" ]; do
  ROOT_DIR="$(dirname "$ROOT_DIR")"
done
if [ ! -x "$ROOT_DIR/.venv/bin/python" ]; then
  echo "Shared environment missing. Initialize <root>/.venv and install requirements.txt first." >&2
  exit 1
fi
"$ROOT_DIR/.venv/bin/python" scripts/prepare_inputs.py --cwd "$ORIG_CWD" > /tmp/stock_report_prepare.json
```

- `prepare_inputs.py` responsibilities:
1. Find project root by walking up from `--cwd` until `config.txt` is found.
2. Read `SUMMARY LENGTH` and parse `<min>-<max>`; default to `200-300` if missing/invalid.
3. Read `MODEL`; default to `gpt-5-mini` if missing/blank.
4. Select latest `<root>/collect_info/*.json` by `mtime`.
5. Extract `topic` and per-field non-empty `context` arrays.
6. Output normalized payload JSON.

## 5) Generate Summaries With LLM
- Read `/tmp/stock_report_prepare.json`.
- Use `model`, `min_words`, and `max_words` from the payload.
- For each field in order:
1. If `contexts` is empty: summary must be exactly `No context available.`
2. Otherwise generate an English summary using only this field's `contexts` and global `topic`.
3. Keep summary in `[min_words, max_words]`.

- Build `/tmp/stock_report_sections.json` with this structure:

```json
{
  "output_txt_path": "...",
  "sections": [
    {"field": "AMD", "summary": "No context available."},
    {"field": "AMZN", "summary": "..."}
  ]
}
```

- Do not add a global intro section.

## 6) Execute Script B (write output)
- Script path: `scripts/write_output.py`
- Run:

```bash
ROOT_DIR="$ORIG_CWD"
while [ "$ROOT_DIR" != "/" ] && [ ! -f "$ROOT_DIR/config.txt" ]; do
  ROOT_DIR="$(dirname "$ROOT_DIR")"
done
"$ROOT_DIR/.venv/bin/python" scripts/write_output.py --payload /tmp/stock_report_sections.json
```

- `write_output.py` writes `<root>/collect_info/<json_stem>.txt` with this exact shape:

```text
=== <FIELD_NAME> ===
Summary: <English summary or fallback>

```

## Reference
- Use `references/output-format.md` for schema and acceptance checks.
