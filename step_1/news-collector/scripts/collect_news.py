import re
import json
import time
import hashlib
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

import requests
import feedparser
from dateutil import parser as dtparser
import trafilatura

def find_skill_root(start_dir: str) -> str:
    """
    Walk upwards from start_dir to find the directory containing config.txt.
    That directory is treated as the skill root.
    """
    cur = os.path.abspath(start_dir)
    while True:
        if os.path.isfile(os.path.join(cur, "config.txt")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            # reached filesystem root
            raise FileNotFoundError(
                f"Cannot find config.txt by walking up from: {start_dir}"
            )
        cur = parent


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

# ----------------------------
# Config parsing
# ----------------------------
def parse_config_txt(path: str) -> Dict[str, str]:
    """
    Parse only these top-level sections:
      COMPANY, DAY RANGE, TOPIC, TOP_K
    Ignore everything else.

    Special handling:
      Inside COMPANY block, lines like:
        AMD: AMD, Advanced Micro Devices, ...
      are treated as content, BUT we must still allow switching to
      DAY RANGE / TOPIC / TOP_K when they appear.
    """
    WANTED = {"COMPANY", "DAY RANGE", "TOPIC", "TOP_K"}

    cfg: Dict[str, str] = {}
    current_key: Optional[str] = None
    buf: List[str] = []

    top_key_re = re.compile(r"^([A-Z0-9_ ]+):\s*(.*)$")

    def flush():
        nonlocal current_key, buf
        if current_key in WANTED:
            cfg[current_key] = "\n".join([b.rstrip() for b in buf]).strip()
        current_key = None
        buf = []

    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            s = raw.rstrip("\n").strip()
            if not s or s.startswith("#"):
                continue

            m = top_key_re.match(s)
            if m:
                k = m.group(1).strip()
                rest = m.group(2).strip()

                # If we're inside COMPANY:
                # - "AMD:" etc should be treated as content
                # - but DAY RANGE / TOPIC / TOP_K must start a new section
                if current_key == "COMPANY" and k not in WANTED:
                    buf.append(s)
                    continue

                # start a new section (wanted or not)
                flush()
                current_key = k
                if rest:
                    buf.append(rest)
                continue

            # normal content line
            if current_key is None:
                continue
            buf.append(s)

    flush()
    return cfg

def split_csv(s: str) -> List[str]:
    return [x.strip() for x in re.split(r"[,\s]+", s.strip()) if x.strip()]


def parse_company_aliases(company_block: str) -> Dict[str, List[str]]:
    """
    Parse cfg["COMPANY"] block like:
      AMD: AMD, Advanced Micro Devices, Advanced Micro Devices Inc
      AMZN: AMZN, Amazon, Amazon.com, Amazon.com Inc

    Returns:
      { "AMD": ["AMD", "Advanced Micro Devices", ...], ... }

    Also supports a plain line with comma-separated tickers:
      AMD,AMZN,NVDA
    """
    mapping: Dict[str, List[str]] = {}
    if not company_block or not company_block.strip():
        return mapping

    for raw in company_block.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        if ":" not in line:
            for t in split_csv(line):
                t2 = t.upper()
                mapping.setdefault(t2, [t2])
            continue

        ticker, rest = line.split(":", 1)
        ticker = ticker.strip().upper()
        aliases = [a.strip() for a in rest.split(",") if a.strip()]
        if not aliases:
            aliases = [ticker]

        # de-dup case-insensitive preserving order
        seen = set()
        out: List[str] = []
        for a in aliases:
            key = a.lower()
            if key not in seen:
                out.append(a)
                seen.add(key)

        # ensure ticker itself exists
        if ticker.lower() not in seen:
            out.insert(0, ticker)

        mapping[ticker] = out

    return mapping


# ----------------------------
# RSS sources
# ----------------------------
@dataclass(frozen=True)
class FeedSource:
    source_name: str
    url_builder: Optional[callable]      # if per-ticker
    static_urls: Optional[List[str]]     # if global feeds


def yahoo_finance_feed_url(ticker: str) -> str:
    return f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"


def seeking_alpha_feed_url(ticker: str) -> str:
    return f"https://seekingalpha.com/api/sa/combined/{ticker}.xml"


SOURCES: List[FeedSource] = [
    FeedSource("Yahoo Finance", yahoo_finance_feed_url, None),
    FeedSource("Seeking Alpha", seeking_alpha_feed_url, None),
    FeedSource("MarketWatch", None, ["http://feeds.marketwatch.com/marketwatch/topstories/"]),
    FeedSource(
        "Reuters",
        None,
        [
            "http://feeds.reuters.com/reuters/businessNews",
            "http://feeds.reuters.com/reuters/companyNews",
            "http://feeds.reuters.com/reuters/technologysectorNews",
        ],
    ),
]


# ----------------------------
# Helpers
# ----------------------------
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}


def canonicalize_url(url: str) -> str:
    """Remove common tracking params and normalize."""
    try:
        u = urlparse(url)
        qs = [
            (k, v)
            for (k, v) in parse_qsl(u.query, keep_blank_values=True)
            if k.lower() not in {
                "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
                "guccounter", "guce_referrer", "guce_referrer_sig",
            }
        ]
        new_q = urlencode(qs, doseq=True)
        return urlunparse((u.scheme, u.netloc, u.path, u.params, new_q, ""))  # drop fragment
    except Exception:
        return url


def parse_entry_date(entry) -> Optional[datetime]:
    """Parse feed entry date into timezone-aware UTC datetime."""
    for key in ("published", "updated", "created"):
        if key in entry and entry[key]:
            try:
                dt = dtparser.parse(entry[key])
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except Exception:
                pass

    for key in ("published_parsed", "updated_parsed"):
        if key in entry and entry[key]:
            try:
                t = entry[key]
                return datetime(*t[:6], tzinfo=timezone.utc)
            except Exception:
                pass

    return None


def text_blob(entry) -> str:
    """Only use title (user requirement)."""
    return (entry.get("title", "") or "").strip()


def compile_alias_regex(aliases: List[str]) -> re.Pattern:
    """
    Build regex for aliases using alnum-boundaries to avoid false positives like 'amazonian'.
    Works better than \\b for aliases containing dots like 'Amazon.com'.
    """
    pats = []
    for a in aliases:
        a2 = re.sub(r"\s+", " ", a.strip())
        if not a2:
            continue
        esc = re.escape(a2).replace(r"\ ", r"\s+")
        pats.append(rf"(?<![A-Za-z0-9]){esc}(?![A-Za-z0-9])")
    if not pats:
        pats = [r"$."]  # match nothing
    return re.compile("|".join(pats), flags=re.IGNORECASE)


def alias_hit(blob: str, alias_re: re.Pattern) -> bool:
    return bool(blob) and bool(alias_re.search(blob))


def parse_topic_terms(topic: str) -> List[str]:
    """
    Parse TOPIC into terms.
    Supports separators: comma, semicolon, pipe, newline
    Supports quoted phrases: "data center demand"
    """
    if not topic or not topic.strip():
        return []

    raw = topic.strip()
    quoted = re.findall(r'"([^"]+)"', raw)
    raw_wo_quotes = re.sub(r'"[^"]+"', " ", raw)
    parts = re.split(r"[,\n;|]+", raw_wo_quotes)

    terms: List[str] = []
    for q in quoted:
        q2 = re.sub(r"\s+", " ", q).strip()
        if q2:
            terms.append(q2)

    for p in parts:
        p2 = re.sub(r"\s+", " ", p).strip()
        if p2:
            terms.append(p2)

    seen = set()
    out: List[str] = []
    for term in terms:
        key = term.lower()
        if key not in seen:
            out.append(term)
            seen.add(key)
    return out


def compile_topic_patterns(topic_terms: List[str]) -> List[re.Pattern]:
    """
    Compile topic terms into robust patterns:
    - Multi-word: allow flexible whitespace/hyphen between words
    - Single token: alnum-boundary
    """
    compiled: List[re.Pattern] = []
    for term in topic_terms:
        t = re.sub(r"\s+", " ", term.strip())
        if not t:
            continue

        if " " in t:
            parts = [re.escape(p) for p in t.split(" ")]
            pat_s = r"(?:\s+|-)+".join(parts)
            compiled.append(re.compile(pat_s, re.IGNORECASE))
        else:
            esc = re.escape(t)
            compiled.append(re.compile(rf"(?<![A-Za-z0-9]){esc}(?![A-Za-z0-9])", re.IGNORECASE))

    return compiled


def topic_hit(text: str, topic_patterns: List[re.Pattern]) -> bool:
    """B-mode: require >=1 topic hit if topic provided."""
    if not topic_patterns:
        return True
    if not text:
        return False
    return any(p.search(text) for p in topic_patterns)


def fetch_feed(url: str, timeout_s: int = 15) -> feedparser.FeedParserDict:
    r = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout_s)
    r.raise_for_status()
    return feedparser.parse(r.content)


def extract_context(url: str, timeout_s: int = 15, max_chars: int = 6000) -> str:
    """Fetch url and extract main article text. Returns '' on failure."""
    try:
        r = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout_s)
        r.raise_for_status()

        html = r.text
        text = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=False,
            favor_precision=True,
        )
        if not text:
            return ""

        text = re.sub(r"\s+", " ", text).strip()
        if len(text) > max_chars:
            text = text[:max_chars] + "…"
        return text
    except Exception:
        return ""


# ----------------------------
# Stage A: Collect candidates (per ticker, alias-only prefilter; title only)
# ----------------------------
def collect_candidates_for_ticker(
    ticker: str,
    alias_re: re.Pattern,
    topic_patterns: List[re.Pattern],
    day_range: int,
) -> List[Dict]:
    now_utc = datetime.now(timezone.utc)
    cutoff = now_utc - timedelta(days=day_range)

    candidates: List[Dict] = []
    seen_links = set()

    feed_urls: List[Tuple[str, str]] = []
    for src in SOURCES:
        if src.static_urls:
            for u in src.static_urls:
                feed_urls.append((src.source_name, u))
        if src.url_builder:
            feed_urls.append((src.source_name, src.url_builder(ticker)))

    for source_name, feed_url in feed_urls:
        try:
            feed = fetch_feed(feed_url)
        except Exception:
            continue

        for entry in getattr(feed, "entries", []) or []:
            link = canonicalize_url(entry.get("link", "") or "")
            title = (entry.get("title", "") or "").strip()
            if not link or not title:
                continue

            dt = parse_entry_date(entry) or now_utc
            if dt < cutoff:
                continue

            blob = title  # title only
            if not alias_hit(blob, alias_re):
                continue

            link_key = hashlib.sha256(link.encode("utf-8")).hexdigest()
            if link_key in seen_links:
                continue
            seen_links.add(link_key)

            # Ranking score (topic is soft bonus in title only)
            base = 2.0
            topic_bonus = 2.0 if topic_hit(blob, topic_patterns) and topic_patterns else 0.0
            hours_ago = max(0.0, (now_utc - dt).total_seconds() / 3600.0)
            recency_bonus = max(0.0, 2.0 - (hours_ago / 24.0))  # ~48h window

            candidates.append(
                {
                    "title": title,
                    "link": link,
                    "source": source_name,
                    "date": dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "_score": float(base + topic_bonus + recency_bonus),
                    "_ts": dt.timestamp(),
                }
            )

    candidates.sort(key=lambda x: (x["_score"], x["_ts"]), reverse=True)
    return candidates


# ----------------------------
# Stage B: Build outputs with strong filtering on extracted context (alias AND topic)
# Output item ONLY: title, link, date, source, context
# ----------------------------
def build_output_for_ticker(
    candidates: List[Dict],
    target_n: int,
    alias_re: re.Pattern,
    topic_patterns: List[re.Pattern],
    min_context_chars: int = 200,
    per_request_sleep_s: float = 0.25,
) -> List[Dict]:
    # group by source
    by_source: Dict[str, List[Dict]] = {}
    for c in candidates:
        by_source.setdefault(c["source"], []).append(c)
    for src in by_source:
        by_source[src].sort(key=lambda x: (x["_score"], x["_ts"]), reverse=True)

    out: List[Dict] = []
    used_links = set()

    def try_add_candidate(c: Dict) -> bool:
        link = c["link"]
        if link in used_links:
            return False

        time.sleep(per_request_sleep_s)
        ctx = extract_context(link, timeout_s=15, max_chars=3000)

        if (not ctx) or (len(ctx.strip()) < min_context_chars):
            return False

        # Context filter:
        #   - Must match ticker/alias in context
        #   - For topic, allow either:
        #       a) topic hit in context, or
        #       b) topic hit in title (milder fallback)
        if not alias_hit(ctx, alias_re):
            return False
        if topic_patterns:
            context_topic_hit = topic_hit(ctx, topic_patterns)
            title_topic_hit = topic_hit(c.get("title", ""), topic_patterns)
            if not (context_topic_hit or title_topic_hit):
                return False

        out.append(
            {
                "title": c["title"],
                "link": link,
                "source": c["source"],
                "date": c["date"],
                "context": ctx,
            }
        )
        used_links.add(link)
        return True

    # 1) Ensure each source tries to contribute at least 1 item if possible
    for src in [s.source_name for s in SOURCES]:
        pool = by_source.get(src, [])
        if not pool:
            continue
        for c in pool:
            if len(out) >= target_n:
                break
            if try_add_candidate(c):
                break

    # 2) Fill the rest by ranking
    if len(out) < target_n:
        for c in candidates:
            if len(out) >= target_n:
                break
            if c["link"] in used_links:
                continue
            try_add_candidate(c)

    return out


def atomic_write_json(path: str, payload: dict) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def main():
    # Directory where collect_news.py is located (independent of invocation cwd)
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Skill root: walk upward until a directory containing config.txt is found
    skill_root = find_skill_root(script_dir)

    # Config path is anchored at skill_root
    config_path = os.path.join(skill_root, "config.txt")
    cfg = parse_config_txt(config_path)

    company_aliases = parse_company_aliases(cfg.get("COMPANY", ""))
    tickers = list(company_aliases.keys())

    # Defaults are only fallback values; config normally provides explicit settings
    day_range = int((cfg.get("DAY RANGE", "12") or "12").splitlines()[0].strip())
    topic_str = (cfg.get("TOPIC", "") or "").strip()
    top_k = int((cfg.get("TOP_K", "2") or "2").splitlines()[0].strip())
    per_ticker_target = top_k + 8

    topic_terms = parse_topic_terms(topic_str)
    topic_patterns = compile_topic_patterns(topic_terms)

    # Output is always written to skill_root/collect_info
    out_dir = os.path.join(skill_root, "collect_info")
    ensure_dir(out_dir)

    out_path = os.path.join(out_dir, datetime.now().strftime("%Y-%m-%d-%H") + ".json")

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "day_range": day_range,
        "per_ticker_target": per_ticker_target,
        "topic":topic_terms,
        "results": {},
    }
    atomic_write_json(out_path, payload)
    print(f"Skill root: {skill_root}")
    print(f"Config:     {config_path}")
    print(f"Output:     {out_path}")

    for ticker in tickers:
        aliases = company_aliases.get(ticker.upper(), [ticker.upper()])
        alias_re = compile_alias_regex(aliases)

        candidates = collect_candidates_for_ticker(
            ticker=ticker,
            alias_re=alias_re,
            topic_patterns=topic_patterns,
            day_range=day_range,
        )

        items = build_output_for_ticker(
            candidates=candidates,
            target_n=per_ticker_target,
            alias_re=alias_re,
            topic_patterns=topic_patterns,
            min_context_chars=200,
            per_request_sleep_s=0.25,
        )

        payload["results"][ticker] = items
        payload["generated_at"] = datetime.now().isoformat(timespec="seconds")

        atomic_write_json(out_path, payload)
        print(f"[{ticker}] wrote {len(items)} items")

    print("Done.")

if __name__ == "__main__":
    main()
