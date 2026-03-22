#!/usr/bin/env python3
"""
Daily Neurogenic Rosacea Research Agent

What it does:
- Searches PubMed for new papers about neurogenic rosacea / related terms
- Optionally searches web news via Tavily if TAVILY_API_KEY is set
- Deduplicates items using seen_items.json
- Summarizes new items using OpenAI Responses API
- Saves a daily markdown digest + raw JSON

Environment variables:
- OPENAI_API_KEY=...
- OPENAI_MODEL=gpt-5 (optional)
- NCBI_EMAIL=you@example.com (recommended by NCBI)
- TAVILY_API_KEY=... (optional)

Install:
    pip install openai requests

Run:
    python neurogenic_rosacea_agent.py --output-dir ./rosacea_digests
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

import urllib3
import httpx
import requests
from openai import OpenAI

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PUBMED_SEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_SUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

PUBMED_TERMS = [
    '"neurogenic rosacea"',
    '"rosacea" AND burning',
    '"rosacea" AND neuropathic',
    '"rosacea" AND "small fiber neuropathy"',
    '"facial erythema" AND neuropathic',
]

NEWS_QUERY = (
    '("neurogenic rosacea" OR ("rosacea" AND neuropathic) OR '
    '("rosacea" AND "small fiber neuropathy") OR ("rosacea" AND burning))'
)


def utc_today() -> str:
    return dt.datetime.utcnow().strftime("%Y-%m-%d")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def search_pubmed(term: str, days_back: int = 30, retmax: int = 10) -> List[str]:
    params = {
        "db": "pubmed",
        "term": term,
        "retmode": "json",
        "sort": "pub date",
        "retmax": retmax,
        "reldate": days_back,
        "datetype": "pdat",
    }
    email = os.getenv("NCBI_EMAIL")
    if email:
        params["email"] = email

    r = requests.get(PUBMED_SEARCH_URL, params=params, timeout=30, verify=False)
    r.raise_for_status()
    data = r.json()
    return data.get("esearchresult", {}).get("idlist", [])


def summarize_pubmed_ids(pmids: List[str]) -> List[Dict[str, Any]]:
    if not pmids:
        return []
    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "json",
    }
    email = os.getenv("NCBI_EMAIL")
    if email:
        params["email"] = email

    r = requests.get(PUBMED_SUMMARY_URL, params=params, timeout=30, verify=False)
    r.raise_for_status()
    data = r.json()
    result = []
    for pmid in pmids:
        item = data.get("result", {}).get(str(pmid), {})
        if not item:
            continue
        result.append(
            {
                "id": f"pubmed:{pmid}",
                "source": "PubMed",
                "title": item.get("title"),
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "published": item.get("pubdate"),
                "journal": item.get("fulljournalname"),
                "authors": [a.get("name") for a in item.get("authors", []) if a.get("name")],
            }
        )
    return result


def search_tavily_news(max_results: int = 10) -> List[Dict[str, Any]]:
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return []

    payload = {
        "api_key": api_key,
        "query": NEWS_QUERY,
        "search_depth": "basic",
        "topic": "news",
        "max_results": max_results,
        "days": 30,
        "include_answer": False,
        "include_raw_content": False,
    }
    r = requests.post("https://api.tavily.com/search", json=payload, timeout=45, verify=False)
    r.raise_for_status()
    data = r.json()

    items = []
    for row in data.get("results", []):
        url = row.get("url")
        items.append(
            {
                "id": f"news:{url}",
                "source": row.get("source") or "News",
                "title": row.get("title"),
                "url": url,
                "published": row.get("published_date") or "",
                "content": row.get("content") or "",
            }
        )
    return items


def dedupe_new_items(items: List[Dict[str, Any]], seen_ids: set[str]) -> List[Dict[str, Any]]:
    out = []
    for item in items:
        item_id = item.get("id")
        if item_id and item_id not in seen_ids:
            out.append(item)
    return out


def build_summary_prompt(items: List[Dict[str, Any]]) -> str:
    return f"""
You are a careful medical research summarizer.

Task:
Summarize the following new items related to neurogenic rosacea for a patient.
Be accurate, cautious, and plain-language.
Do NOT claim treatment efficacy unless supported by the item itself.
Separate:
1. What is actually new
2. Why it may matter clinically
3. Whether it is relevant to neurogenic rosacea specifically
4. A very short "bottom line for me" section

Write in Hebrew.
Keep it concise but useful.

Items JSON:
{json.dumps(items, ensure_ascii=False, indent=2)}
""".strip()


def summarize_with_openai(items: List[Dict[str, Any]]) -> str:
    if not items:
        return "לא נמצאו פריטים חדשים היום."

    client = OpenAI(
        api_key=os.environ["OPENAI_API_KEY"],
        http_client=httpx.Client(verify=False),
    )
    model = os.getenv("OPENAI_MODEL", "gpt-5")

    prompt = build_summary_prompt(items)
    response = client.responses.create(
        model=model,
        input=prompt,
    )
    return response.output_text.strip()


def render_markdown(date_str: str, items: List[Dict[str, Any]], summary: str) -> str:
    lines = [
        f"# Neurogenic Rosacea Daily Digest — {date_str}",
        "",
        "## סיכום",
        "",
        summary,
        "",
        "## פריטים חדשים",
        "",
    ]
    if not items:
        lines.append("לא נמצאו פריטים חדשים.")
    else:
        for item in items:
            lines.extend(
                [
                    f"### {item.get('title', 'ללא כותרת')}",
                    f"- מקור: {item.get('source', '')}",
                    f"- תאריך: {item.get('published', '')}",
                    f"- קישור: {item.get('url', '')}",
                ]
            )
            if item.get("journal"):
                lines.append(f"- כתב עת: {item.get('journal')}")
            if item.get("authors"):
                lines.append(f"- מחברים: {', '.join(item['authors'][:5])}")
            if item.get("content"):
                lines.append(f"- תקציר קצר מהכתבה: {item.get('content')[:400]}")
            lines.append("")
    return "\n".join(lines).strip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="./rosacea_digests")
    parser.add_argument("--days-back", type=int, default=30)
    parser.add_argument("--pubmed-retmax", type=int, default=10)
    parser.add_argument("--news-retmax", type=int, default=10)
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Missing OPENAI_API_KEY")

    out_dir = Path(args.output_dir)
    ensure_dir(out_dir)

    seen_path = out_dir / "seen_items.json"
    raw_path = out_dir / f"raw_{utc_today()}.json"
    md_path = out_dir / f"digest_{utc_today()}.md"

    seen_ids = set(load_json(seen_path, []))

    pubmed_ids: List[str] = []
    for term in PUBMED_TERMS:
        try:
            pubmed_ids.extend(search_pubmed(term, days_back=args.days_back, retmax=args.pubmed_retmax))
        except Exception as e:
            print(f"[warn] PubMed search failed for {term}: {e}")

    pubmed_ids = list(dict.fromkeys(pubmed_ids))
    pubmed_items = summarize_pubmed_ids(pubmed_ids)

    try:
        news_items = search_tavily_news(max_results=args.news_retmax)
    except Exception as e:
        print(f"[warn] News search failed: {e}")
        news_items = []

    all_items = pubmed_items + news_items
    new_items = dedupe_new_items(all_items, seen_ids)

    summary = summarize_with_openai(new_items)
    save_json(raw_path, new_items)
    md = render_markdown(utc_today(), new_items, summary)
    md_path.write_text(md, encoding="utf-8")

    seen_ids.update(item["id"] for item in new_items if item.get("id"))
    save_json(seen_path, sorted(seen_ids))

    print(f"Saved digest to: {md_path}")
    print(f"Saved raw items to: {raw_path}")
    print(f"New items found: {len(new_items)}")


if __name__ == "__main__":
    main()
