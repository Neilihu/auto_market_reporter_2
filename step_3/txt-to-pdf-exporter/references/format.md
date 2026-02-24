# I/O Contract

## Input Selection
- Default source directory: `<root>/collect_info`
- Default source file: latest `*.txt` by modification time
- Optional override: `--input-txt`

## Root Resolution
- Start from `--cwd` (or current directory if omitted)
- Walk up parent directories until `config.txt` is found
- That directory is `<root>`

## Output Path
- Read `PDF OUTPUT DIR` from `<root>/config.txt`
- If missing/blank, default to `collect_info`
- Relative path resolves against `<root>`
- Final output filename: `<input_txt_stem>.pdf`

## Font Size
- Read `PDF FONT SIZE` from `<root>/config.txt`
- Value is parsed as integer
- Missing/invalid value defaults to `11`
- Value is clamped into `8..18`
- It affects body text, section titles, cover title/subtitle, and link block text
- Page number font remains fixed

## Error Conditions
- Missing `config.txt`
- Missing `<root>/collect_info`
- No txt files in collect_info
- Missing `fpdf2` package

## Acceptance Checks
- Latest txt is selected when no override is provided
- PDF filename stem matches source txt stem
- Output directory follows `PDF OUTPUT DIR` setting
- Script prints generated PDF path on success
