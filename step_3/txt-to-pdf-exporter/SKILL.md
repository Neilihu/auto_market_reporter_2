---
name: txt-to-pdf-exporter
description: Convert the latest summary TXT file in collect_info into a same-name PDF. Use when users ask to export the latest text summary as PDF, keep filename parity, and route output with config.txt PDF OUTPUT DIR.
---

# TXT To PDF Exporter Workflow

Follow this flow exactly.

## 1) Run The Conversion Script
- Before running the script, ensure `config.txt` is available and readable from the run context.
- The script must read both `PDF OUTPUT DIR` and `PDF FONT SIZE` from `config.txt` before rendering.
- Before running scripts, verify `<root>/.venv/bin/python` exists. If missing, stop and report:
`Shared environment missing. Initialize <root>/.venv and install requirements.txt first.`
- Execute script directly from the skill directory:

```bash
ORIG_CWD="$PWD"
if [ -d "$PWD/step_3/txt-to-pdf-exporter" ]; then
  cd "$PWD/step_3/txt-to-pdf-exporter"
fi
ROOT_DIR="$ORIG_CWD"
while [ "$ROOT_DIR" != "/" ] && [ ! -f "$ROOT_DIR/config.txt" ]; do
  ROOT_DIR="$(dirname "$ROOT_DIR")"
done
if [ ! -x "$ROOT_DIR/.venv/bin/python" ]; then
  echo "Shared environment missing. Initialize <root>/.venv and install requirements.txt first." >&2
  exit 1
fi
"$ROOT_DIR/.venv/bin/python" scripts/txt_to_pdf.py --cwd "$ORIG_CWD"
```

## 2) Script Responsibilities
`scripts/txt_to_pdf.py` handles all conversion logic:
- Walk up from `--cwd` to locate the first `config.txt`.
- Read `PDF OUTPUT DIR` from `config.txt`; default to `collect_info` if missing/blank.
- Find latest `*.txt` in `<root>/collect_info` when `--input-txt` is not provided.
- Convert full txt content to PDF using `fpdf2` with line wrapping and automatic page breaks.
- Write output as same-name `.pdf` under resolved output directory.

## 3) Output Contract
- Output path printed to stdout (one line).
- Filename matches txt stem.
- No content summarization or text rewriting in this skill; it only converts txt to pdf.

## 4) Failure Handling
- If script exits non-zero, stop and return script error.
- Expected error conditions:
  - `config.txt not found while walking up from current directory`
  - `collect_info directory not found`
  - `No TXT files found in collect_info`
  - `fpdf2 is required. Install it with: pip install fpdf2`

## Reference
- See `references/format.md` for I/O details and acceptance checks.
