#!/usr/bin/env python3
import argparse
import json
import re
import sys
from typing import Any, Dict, List

import requests

YAHOO_QUOTE_URL = "https://query1.finance.yahoo.com/v7/finance/quote"
YAHOO_SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search"

US_EXCH_HINTS = {
    "NMS",  # NasdaqGS
    "NGM",  # NasdaqGM
    "NCM",  # NasdaqCM
    "NYQ",  # NYSE
    "ASE",  # NYSE American
    "PCX",  # NYSE Arca
    "BTS",  # BATS
}


def is_us_equity(item: Dict[str, Any]) -> bool:
    quote_type = str(item.get("quoteType") or item.get("typeDisp") or "").upper()
    if quote_type and quote_type not in {"EQUITY", "MUTUALFUND", "ETF"}:
        return False

    exchange = str(item.get("exchange") or item.get("exch") or "").upper()
    exchange_disp = str(item.get("fullExchangeName") or item.get("exchDisp") or "").upper()
    region = str(item.get("region") or "").upper()

    if exchange in US_EXCH_HINTS:
        return True
    if "NASDAQ" in exchange_disp or "NEW YORK" in exchange_disp or "NYSE" in exchange_disp:
        return True
    if region == "US":
        return True
    return False


def normalize_match(item: Dict[str, Any], source: str) -> Dict[str, str]:
    return {
        "symbol": str(item.get("symbol") or "").upper(),
        "name": str(item.get("longName") or item.get("shortName") or item.get("name") or ""),
        "exchange": str(item.get("fullExchangeName") or item.get("exchDisp") or item.get("exchange") or item.get("exch") or ""),
        "region": str(item.get("region") or ""),
        "quote_type": str(item.get("quoteType") or item.get("typeDisp") or ""),
        "source": source,
    }


def fetch_exact(symbol: str, timeout: int) -> Dict[str, Any]:
    resp = requests.get(
        YAHOO_QUOTE_URL,
        params={"symbols": symbol},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    results = data.get("quoteResponse", {}).get("result", [])
    return results[0] if results else {}


def fetch_lookup(query: str, timeout: int) -> List[Dict[str, Any]]:
    resp = requests.get(
        YAHOO_SEARCH_URL,
        params={"q": query, "quotesCount": 8, "newsCount": 0},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    quotes = data.get("quotes", [])
    return quotes if isinstance(quotes, list) else []


def resolve_us_ticker(query: str, timeout: int) -> Dict[str, Any]:
    raw = (query or "").strip()
    if not raw:
        return {
            "input": query,
            "status": "not_found",
            "matches": [],
            "message": "Empty query.",
        }

    ticker_like = raw.upper()
    if re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,9}", ticker_like):
        try:
            exact = fetch_exact(ticker_like, timeout)
            if exact and is_us_equity(exact):
                return {
                    "input": raw,
                    "status": "resolved_exact",
                    "matches": [normalize_match(exact, "yahoo_quote")],
                    "message": "Input is a valid US-listed symbol.",
                }
        except Exception as exc:
            # Continue to lookup pass.
            _ = exc

    try:
        lookup_results = fetch_lookup(raw, timeout)
    except Exception as exc:
        return {
            "input": raw,
            "status": "not_found",
            "matches": [],
            "message": f"Lookup failed: {exc}",
        }

    filtered: List[Dict[str, str]] = []
    seen = set()
    for item in lookup_results:
        if not is_us_equity(item):
            continue
        normalized = normalize_match(item, "yahoo_search")
        symbol = normalized.get("symbol", "")
        if not symbol or symbol in seen:
            continue
        filtered.append(normalized)
        seen.add(symbol)
        if len(filtered) >= 3:
            break

    if filtered:
        return {
            "input": raw,
            "status": "resolved_from_lookup",
            "matches": filtered,
            "message": "Lookup found US-listed mapping candidates. Require user confirmation before adding.",
        }

    return {
        "input": raw,
        "status": "not_found",
        "matches": [],
        "message": "No reliable US-listed ticker mapping found.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve whether input maps to a US-listed ticker.")
    parser.add_argument("--query", required=True, help="Ticker, company name, or raw user input.")
    parser.add_argument("--timeout", type=int, default=10)
    args = parser.parse_args()

    try:
        out = resolve_us_ticker(args.query, args.timeout)
    except Exception as exc:
        out = {
            "input": args.query,
            "status": "not_found",
            "matches": [],
            "message": f"Unexpected error: {exc}",
        }

    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
