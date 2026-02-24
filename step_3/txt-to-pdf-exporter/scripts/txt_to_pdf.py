#!/usr/bin/env python3
"""Convert latest collect_info txt file to pdf."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import re
import sys
from pathlib import Path


def fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)


def find_root_from(start_dir: Path) -> Path:
    cur = start_dir.resolve()
    for candidate in [cur, *cur.parents]:
        if (candidate / "config.txt").is_file():
            return candidate
    fail("config.txt not found while walking up from current directory")


def parse_config_sections(config_path: Path) -> dict[str, str]:
    section_re = re.compile(r"^([A-Z0-9_ ]+):\s*(.*)$")
    out: dict[str, list[str]] = {}
    key: str | None = None

    for raw in config_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = section_re.match(line)
        if m:
            key = m.group(1).strip()
            out.setdefault(key, [])
            rest = m.group(2).strip()
            if rest:
                out[key].append(rest)
            continue
        if key is not None:
            out[key].append(line)

    return {k: "\n".join(v).strip() for k, v in out.items()}


def resolve_output_dir(root: Path, cfg: dict[str, str]) -> Path:
    value = cfg.get("PDF OUTPUT DIR", "").strip()
    if not value:
        value = "collect_info"
    out = Path(value)
    if not out.is_absolute():
        out = root / out
    return out


def parse_pdf_font_size(cfg: dict[str, str]) -> int:
    raw = cfg.get("PDF FONT SIZE", "").strip()
    default = 11
    if not raw:
        return default
    try:
        value = int(raw.splitlines()[0].strip())
    except ValueError:
        return default
    return max(8, min(18, value))


def latest_txt(collect_info_dir: Path) -> Path:
    txt_files = sorted(
        collect_info_dir.glob("*.txt"),
        key=lambda p: (p.stat().st_mtime, p.name),
    )
    if not txt_files:
        fail("No TXT files found in collect_info")
    return txt_files[-1]


def choose_input_txt(root: Path, user_value: str | None) -> Path:
    collect_info_dir = root / "collect_info"
    if not collect_info_dir.is_dir():
        fail("collect_info directory not found")

    if not user_value:
        return latest_txt(collect_info_dir)

    candidate = Path(user_value)
    if not candidate.is_absolute():
        candidate = root / candidate
    if not candidate.is_file():
        fail(f"input txt not found: {candidate}")
    if candidate.suffix.lower() != ".txt":
        fail(f"input file must be .txt: {candidate}")
    return candidate


class ReportPDF:
    """Wrapper around fpdf2 rendering with a consistent report style."""

    def __init__(self, base_font_size: int) -> None:
        try:
            from fpdf import FPDF
        except ImportError:
            fail("fpdf2 is required. Install it with: pip install fpdf2")

        class _Doc(FPDF):
            def header(self) -> None:  # type: ignore[override]
                # Hide page number on cover (physical page 1).
                if self.page_no() <= 1:
                    return
                display_page = self.page_no() - 1
                self.set_y(10)
                self.set_font("Helvetica", size=9)
                self.set_text_color(110, 110, 110)
                self.cell(0, 6, f"Page {display_page}", align="R")

        self.pdf = _Doc(format="A4")
        self.pdf.set_auto_page_break(auto=True, margin=15)
        self.pdf.set_margins(18, 18, 18)
        self.base_font_size = max(8, min(18, base_font_size))
        self.body_font_size = self.base_font_size
        self.section_title_font_size = self.base_font_size + 4
        self.cover_title_font_size = self.base_font_size + 11
        self.cover_subtitle_font_size = self.base_font_size + 2
        self.links_header_font_size = self.base_font_size
        self.link_text_font_size = max(8, self.base_font_size - 1)

    @staticmethod
    def sanitize(text: str) -> str:
        # Built-in fonts handle latin-1 only; replace unsupported chars.
        return text.encode("latin-1", "replace").decode("latin-1")

    def add_cover_page(self, stem: str, companies: list[str]) -> None:
        self.pdf.add_page()
        self.pdf.set_text_color(30, 48, 80)
        self.pdf.set_font("Helvetica", style="B", size=self.cover_title_font_size)
        self.pdf.ln(55)
        self.pdf.cell(0, 12, "Stock Summary Report", align="C", new_x="LMARGIN", new_y="NEXT")

        self.pdf.set_font("Helvetica", size=self.cover_subtitle_font_size)
        self.pdf.set_text_color(80, 80, 80)
        self.pdf.ln(7)

        if not companies:
            companies = ["General"]
        for company in companies:
            self.pdf.cell(0, 8, self.sanitize(company), align="C", new_x="LMARGIN", new_y="NEXT")

        self.pdf.ln(5)
        self.pdf.set_font("Helvetica", size=self.cover_subtitle_font_size)
        self.pdf.cell(0, 8, datetime.now().strftime("Generated on %Y-%m-%d %H:%M"), align="C", new_x="LMARGIN", new_y="NEXT")

        y = self.pdf.get_y() + 10
        self.pdf.set_draw_color(56, 96, 160)
        self.pdf.line(32, y, 178, y)

    def add_section_title(self, title: str) -> None:
        self.pdf.set_font("Helvetica", style="B", size=self.section_title_font_size)
        self.pdf.set_text_color(30, 48, 80)
        self.pdf.ln(6)
        self.pdf.cell(0, 9, self.sanitize(title), new_x="LMARGIN", new_y="NEXT")
        y = self.pdf.get_y()
        self.pdf.set_draw_color(120, 140, 180)
        self.pdf.line(18, y, 192, y)
        self.pdf.ln(3)

    def add_paragraph(self, text: str) -> None:
        self.pdf.set_font("Helvetica", size=self.body_font_size)
        self.pdf.set_text_color(20, 20, 20)
        clean = self.sanitize(text.strip())
        if not clean:
            self.pdf.ln(4)
            return
        # Prefer word-based wrapping so regular words are never split across lines.
        try:
            self.pdf.multi_cell(0, 6, clean, new_x="LMARGIN", new_y="NEXT", wrapmode="WORD")
        except Exception:
            # Fallback for rare very long unbreakable tokens (e.g., URLs without spaces).
            softened = re.sub(r"(\S{40})(?=\S)", r"\1 ", clean)
            self.pdf.multi_cell(0, 6, softened, new_x="LMARGIN", new_y="NEXT", wrapmode="WORD")
        self.pdf.ln(2)

    def add_links_block(self, items: list[dict[str, str]]) -> None:
        if not items:
            return
        self.pdf.ln(8)
        self.pdf.set_font("Helvetica", style="B", size=self.links_header_font_size)
        self.pdf.set_text_color(55, 55, 55)
        self.pdf.cell(0, 7, "Related Links", new_x="LMARGIN", new_y="NEXT")
        self.pdf.ln(1)

        for item in items:
            title = self.sanitize(item.get("title", "").strip())
            link = item.get("link", "").strip()
            if not title or not link:
                continue

            # Title line
            self.pdf.set_font("Helvetica", size=self.link_text_font_size)
            self.pdf.set_text_color(60, 60, 60)
            self.pdf.multi_cell(0, 5.5, title, new_x="LMARGIN", new_y="NEXT", wrapmode="WORD")

            # Clickable URL line
            self.pdf.set_font("Helvetica", size=self.link_text_font_size)
            self.pdf.set_text_color(30, 80, 170)
            try:
                self.pdf.multi_cell(0, 5.5, link, link=link, new_x="LMARGIN", new_y="NEXT", wrapmode="WORD")
            except Exception:
                # Graceful fallback when hyperlink rendering fails.
                softened = re.sub(r"(\S{40})(?=\S)", r"\1 ", link)
                self.pdf.multi_cell(0, 5.5, softened, new_x="LMARGIN", new_y="NEXT", wrapmode="WORD")

            self.pdf.ln(2)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.pdf.output(str(path))


def parse_sections(text: str) -> list[dict[str, list[str] | str]]:
    header_re = re.compile(r"^===\s*(.+?)\s*===\s*$")
    sections: list[dict[str, list[str] | str]] = []
    current_title: str | None = None
    paragraph_lines: list[str] = []
    current_paragraphs: list[str] = []

    def flush_paragraph() -> None:
        if paragraph_lines:
            para = " ".join(x.strip() for x in paragraph_lines if x.strip()).strip()
            if para:
                current_paragraphs.append(para)
            paragraph_lines.clear()

    def flush_section() -> None:
        nonlocal current_title, current_paragraphs
        flush_paragraph()
        if current_title is None and current_paragraphs:
            sections.append({"title": "General", "paragraphs": current_paragraphs[:]})
        elif current_title is not None:
            sections.append({"title": current_title, "paragraphs": current_paragraphs[:]})
        current_paragraphs = []

    for raw in text.splitlines():
        line = raw.rstrip()
        m = header_re.match(line)
        if m:
            flush_section()
            current_title = m.group(1).strip()
            continue

        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            continue

        if stripped.startswith("Summary:"):
            stripped = stripped[len("Summary:") :].strip()
        paragraph_lines.append(stripped)

    flush_section()
    return sections


def load_links_by_ticker(input_txt: Path) -> dict[str, list[dict[str, str]]]:
    json_path = input_txt.with_suffix(".json")
    if not json_path.is_file():
        return {}

    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"Warning: failed to parse JSON for links: {exc}", file=sys.stderr)
        return {}

    if not isinstance(payload, dict):
        return {}
    results = payload.get("results")
    if not isinstance(results, dict):
        return {}

    out: dict[str, list[dict[str, str]]] = {}
    for ticker, rows in results.items():
        if not isinstance(ticker, str) or not isinstance(rows, list):
            continue
        links: list[dict[str, str]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            title = row.get("title")
            link = row.get("link")
            if isinstance(title, str) and isinstance(link, str):
                t = title.strip()
                l = link.strip()
                if t and l:
                    links.append({"title": t, "link": l})
            if len(links) >= 3:
                break
        if links:
            out[ticker] = links

    return out


def build_pdf(input_txt: Path, output_pdf: Path, base_font_size: int) -> None:
    text = input_txt.read_text(encoding="utf-8", errors="replace")

    sections = parse_sections(text)
    if not sections:
        sections = [{"title": "General", "paragraphs": ["No content available."]}]
    links_by_ticker = load_links_by_ticker(input_txt)

    companies: list[str] = []
    seen: set[str] = set()
    for section in sections:
        title = str(section["title"]).strip()  # type: ignore[index]
        if title and title not in seen:
            companies.append(title)
            seen.add(title)

    report = ReportPDF(base_font_size=base_font_size)
    report.add_cover_page(input_txt.stem, companies)

    for section in sections:
        # Force each company/section to start on a new page.
        report.pdf.add_page()
        section_title = str(section["title"])
        report.add_section_title(section_title)
        for para in section["paragraphs"]:  # type: ignore[index]
            report.add_paragraph(str(para))
        report.add_links_block(links_by_ticker.get(section_title, []))

    report.save(output_pdf)


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert latest collect_info txt to pdf.")
    parser.add_argument("--cwd", default=".", help="Run context for locating project root.")
    parser.add_argument("--input-txt", help="Optional txt path. Defaults to latest in collect_info.")
    args = parser.parse_args()

    root = find_root_from(Path(args.cwd))
    cfg = parse_config_sections(root / "config.txt")
    input_txt = choose_input_txt(root, args.input_txt)
    output_dir = resolve_output_dir(root, cfg)
    output_pdf = output_dir / f"{input_txt.stem}.pdf"
    pdf_font_size = parse_pdf_font_size(cfg)

    build_pdf(input_txt, output_pdf, pdf_font_size)
    print(str(output_pdf))


if __name__ == "__main__":
    main()
