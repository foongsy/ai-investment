#!/usr/bin/env python3
"""Export Trading Proposals for one Research Run to a TradingView watchlist."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

NOTION_VERSION = "2025-09-03"
BASE_URL = "https://api.notion.com/v1"
TV_SEARCH_URL = "https://symbol-search.tradingview.com/symbol_search/v3/"
TV_HEADERS = {
    "Origin": "https://www.tradingview.com",
    "Referer": "https://www.tradingview.com/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}

RUNS_TITLES = ("Research Runs",)
PROPOSALS_TITLES = ("Trading Proposals", "Trade Proposals", "Proposals")

RUNS_REQUIRED = ("Run ID",)
PROPOSALS_REQUIRED = ("Proposal", "Ticker", "Market", "Run")

MARKET_ORDER = ("HK", "JP", "US", "OTHER")
SECTION_HEADERS = {"HK": "###HK", "JP": "###JP", "US": "###US", "OTHER": "###OTHER"}

EXCHANGE_MAP = {
    "NASDAQ": "NASDAQ",
    "NYSE": "NYSE",
    "AMEX": "AMEX",
    "HKEX": "HKEX",
    "HONG KONG": "HKEX",
    "TSE": "TSE",
    "TOKYO": "TSE",
}

MARKET_EXCHANGE = {"HK": "HKEX", "JP": "TSE"}
MARKET_COUNTRY = {"HK": "HK", "JP": "JP", "US": "US"}


class ExportError(Exception):
    pass


def load_env(name: str) -> str:
    value = os.environ.get(name)
    if value:
        return value.strip()
    env_path = Path.cwd() / ".env"
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise ExportError(f"{name} is missing from environment or .env")


def notion_request(
    method: str,
    path: str,
    token: str,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ExportError(f"Notion API {method} {path} failed ({exc.code}): {detail}") from exc


def paginate_query(
    token: str,
    data_source_id: str,
    body: dict[str, Any],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    start_cursor: str | None = None
    while True:
        payload = dict(body)
        if start_cursor:
            payload["start_cursor"] = start_cursor
        data = notion_request(
            "POST",
            f"/data_sources/{data_source_id}/query",
            token,
            payload,
        )
        results.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        start_cursor = data.get("next_cursor")
        if not start_cursor:
            break
        time.sleep(0.35)
    return results


def search_data_source(token: str, titles: tuple[str, ...]) -> dict[str, Any]:
    for title in titles:
        data = notion_request(
            "POST",
            "/search",
            token,
            {
                "query": title,
                "filter": {"property": "object", "value": "data_source"},
                "page_size": 20,
            },
        )
        for item in data.get("results", []):
            if item.get("object") != "data_source":
                continue
            plain = "".join(part.get("plain_text", "") for part in item.get("title", []))
            if plain == title:
                return item
        time.sleep(0.35)
    raise ExportError(f"Could not find Notion data source. Tried: {', '.join(titles)}")


def validate_schema(data_source: dict[str, Any], required: tuple[str, ...]) -> None:
    props = data_source.get("properties", {})
    missing = [name for name in required if name not in props]
    if missing:
        title = "".join(part.get("plain_text", "") for part in data_source.get("title", []))
        raise ExportError(
            f"Data source '{title}' is missing required properties: {', '.join(missing)}"
        )


def plain_text(prop: dict[str, Any] | None) -> str | None:
    if not prop:
        return None
    if prop.get("type") == "title":
        parts = prop.get("title") or []
    elif prop.get("type") == "rich_text":
        parts = prop.get("rich_text") or []
    else:
        return None
    text = "".join(part.get("plain_text", "") for part in parts).strip()
    return text or None


def select_name(prop: dict[str, Any] | None) -> str | None:
    if not prop or prop.get("type") != "select":
        return None
    selected = prop.get("select")
    if not selected:
        return None
    return selected.get("name")


def relation_ids(prop: dict[str, Any] | None) -> list[str]:
    if not prop or prop.get("type") != "relation":
        return []
    return [item["id"] for item in (prop.get("relation") or [])]


def map_exchange_from_text(exchange: str | None) -> str | None:
    if not exchange:
        return None
    upper = exchange.upper()
    for key, value in EXCHANGE_MAP.items():
        if key in upper:
            return value
    return None


def search_type_from_asset_class(asset_class: str | None) -> str:
    mapping = {"equity": "stock", "etf": "etf", "crypto": "crypto"}
    if not asset_class:
        return "stock"
    return mapping.get(asset_class.lower(), "stock")


def normalize_search_text(ticker: str, market: str | None) -> str:
    text = ticker.strip()
    market = (market or "").upper()
    if market == "HK":
        text = re.sub(r"\.HK$", "", text, flags=re.IGNORECASE)
        if text.isdigit():
            text = text.lstrip("0") or "0"
    elif market == "JP":
        text = re.sub(r"\.T$", "", text, flags=re.IGNORECASE)
    return text


def build_tv_params(proposal: dict[str, Any]) -> dict[str, str]:
    market = (proposal.get("market") or "OTHER").upper()
    ticker = proposal.get("ticker") or ""
    exchange = proposal.get("exchange")
    asset_class = proposal.get("asset_class")

    params: dict[str, str] = {
        "text": normalize_search_text(ticker, market),
        "lang": "en",
        "search_type": search_type_from_asset_class(asset_class),
        "domain": "production",
    }

    tv_exchange = map_exchange_from_text(exchange)
    if market in MARKET_EXCHANGE:
        tv_exchange = MARKET_EXCHANGE[market]
    if tv_exchange:
        params["exchange"] = tv_exchange

    country = MARKET_COUNTRY.get(market)
    if country:
        params["country"] = country
        params["sort_by_country"] = country

    return params


def tv_search(params: dict[str, str]) -> dict[str, Any]:
    query = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{TV_SEARCH_URL}?{query}", headers=TV_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ExportError(f"TradingView search failed ({exc.code}): {detail}") from exc


def build_tv_id(hit: dict[str, Any]) -> str:
    prefix = (hit.get("prefix") or "").strip()
    symbol = hit.get("symbol") or ""
    if prefix:
        return f"{prefix}:{symbol}"
    exchange = (hit.get("exchange") or "").split(",")[0].strip().upper()
    return f"{exchange}:{symbol}"


def score_hit(
    hit: dict[str, Any],
    proposal: dict[str, Any],
    search_text: str,
    expected_exchange: str | None,
    search_type: str,
) -> int:
    score = 0
    market = (proposal.get("market") or "OTHER").upper()
    company = (proposal.get("company_name") or "").lower()
    asset_class = (proposal.get("asset_class") or "").lower()

    hit_prefix = (hit.get("prefix") or "").upper()
    hit_exchange = (hit.get("exchange") or "").split(",")[0].strip().upper()
    hit_symbol = (hit.get("symbol") or "").upper()
    hit_type = (hit.get("type") or "").lower()
    hit_country = (hit.get("country") or "").upper()
    hit_desc = (hit.get("description") or "").lower()

    if expected_exchange and (
        hit_prefix == expected_exchange or hit_exchange == expected_exchange
    ):
        score += 10
    if hit_symbol == search_text.upper():
        score += 10
    if asset_class == "etf" and hit_type in {"fund", "etf"}:
        score += 5
    elif asset_class == "crypto" and hit_type == "crypto":
        score += 5
    elif asset_class in {"", "equity"} and hit_type in {"stock", "dr"}:
        score += 5
    elif search_type == hit_type:
        score += 5
    if company and company in hit_desc:
        score += 3
    if market == "US" and hit_country == "US":
        score += 5
    elif market == "HK" and hit_country in {"HK", "CN"}:
        score += 5
    elif market == "JP" and hit_country == "JP":
        score += 5
    return score


def resolve_tv_symbol(proposal: dict[str, Any]) -> dict[str, Any]:
    params = build_tv_params(proposal)
    search_text = params["text"]
    expected_exchange = params.get("exchange")
    search_type = params["search_type"]

    def pick(data: dict[str, Any]) -> dict[str, Any]:
        symbols = data.get("symbols") or []
        if not symbols:
            return {"status": "failed", "reason": "no symbols returned"}
        scored = [
            (score_hit(hit, proposal, search_text, expected_exchange, search_type), build_tv_id(hit), hit)
            for hit in symbols
        ]
        scored.sort(key=lambda item: item[0], reverse=True)
        best_score, best_id, _ = scored[0]
        if best_score < 10:
            return {"status": "ambiguous", "reason": f"low confidence score {best_score}"}
        if len(scored) > 1 and scored[0][0] - scored[1][0] <= 3:
            return {
                "status": "ambiguous",
                "reason": f"top scores tied within 3 ({scored[0][0]} vs {scored[1][0]})",
            }
        return {"status": "resolved", "tv_id": best_id, "score": best_score}

    try:
        result = pick(tv_search(params))
        if result["status"] == "failed" and proposal.get("company_name"):
            retry_params = dict(params)
            retry_params["text"] = proposal["company_name"]
            time.sleep(1)
            result = pick(tv_search(retry_params))
        return result
    except ExportError as exc:
        return {"status": "failed", "reason": str(exc)}


def parse_proposal_row(row: dict[str, Any]) -> dict[str, Any]:
    props = row.get("properties", {})
    return {
        "page_id": row["id"],
        "proposal": plain_text(props.get("Proposal")),
        "ticker": plain_text(props.get("Ticker")),
        "market": select_name(props.get("Market")),
        "exchange": plain_text(props.get("Exchange")),
        "asset_class": select_name(props.get("Asset Class")),
        "company_name": plain_text(props.get("Company Name")),
    }


def resolve_run(
    token: str,
    runs_ds_id: str,
    run_id: str | None,
) -> tuple[str, str, str]:
    if run_id:
        rows = paginate_query(
            token,
            runs_ds_id,
            {
                "filter": {"property": "Run ID", "title": {"equals": run_id}},
                "page_size": 100,
            },
        )
        if not rows:
            raise ExportError(f"run_id not found: {run_id}")
        if len(rows) > 1:
            ids = ", ".join(row["id"] for row in rows)
            raise ExportError(f"Multiple Research Runs rows match run_id {run_id}: {ids}")
        source = "supplied"
    else:
        rows = paginate_query(
            token,
            runs_ds_id,
            {
                "filter": {"property": "Run ID", "title": {"is_not_empty": True}},
                "sorts": [{"timestamp": "created_time", "direction": "descending"}],
                "page_size": 1,
            },
        )
        if not rows:
            raise ExportError("No Research Runs rows with a non-empty Run ID")
        source = "latest_created"

    row = rows[0]
    resolved_run_id = plain_text(row["properties"].get("Run ID"))
    if not resolved_run_id:
        raise ExportError("Matched Research Runs row has empty Run ID")
    return resolved_run_id, row["id"], source


def build_watchlist(resolved_rows: list[dict[str, Any]]) -> str:
    by_market: dict[str, list[str]] = {market: [] for market in MARKET_ORDER}
    for row in resolved_rows:
        if row.get("status") != "resolved":
            continue
        market = (row.get("market") or "OTHER").upper()
        if market not in by_market:
            market = "OTHER"
        by_market[market].append(row["tv_id"])

    lines: list[str] = []
    for market in MARKET_ORDER:
        ids = sorted(set(by_market[market]))
        if not ids:
            continue
        lines.append(SECTION_HEADERS[market])
        lines.extend(ids)
        lines.append("")
    return "\n".join(lines).rstrip() + ("\n" if lines else "")


def fastio_cmd(*args: str) -> dict[str, Any]:
    fastio_bin = os.environ.get("FASTIO_BIN", "fastio")
    token = load_env("FASTIO_API_KEY")
    cmd = [fastio_bin, *args, "--token", token, "--format", "json"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise ExportError(
            f"fastio {' '.join(args)} failed ({result.returncode}): {result.stderr or result.stdout}"
        )
    return json.loads(result.stdout)


def folder_id_by_name(ws_id: str, parent_id: str | None, name: str) -> str | None:
    args = ["files", "list", "--workspace", ws_id]
    if parent_id:
        args += ["--folder", parent_id]
    items = fastio_cmd(*args).get("nodes", {}).get("items", [])
    match = next((n for n in items if n.get("type") == "folder" and n.get("name") == name), None)
    return match["id"] if match else None


def ensure_folder(ws_id: str, parent_id: str | None, name: str) -> str:
    existing = folder_id_by_name(ws_id, parent_id, name)
    if existing:
        return existing
    args = ["files", "create-folder", "--workspace", ws_id, name]
    if parent_id:
        args = ["files", "create-folder", "--workspace", ws_id, "--parent", parent_id, name]
    created = fastio_cmd(*args)
    return created.get("folder_id") or created["node"]["id"]


def upload_fastio_session(
    local_path: Path,
    watchlist_content: str,
    export_date: str,
    run_id: str,
    overwrite: bool,
) -> dict[str, Any]:
    ws_name = load_env("FASTIO_WORKSPACE_NAME")
    workspaces = fastio_cmd("workspace", "list").get("workspaces", [])
    ws_id = next((w["id"] for w in workspaces if w["name"] == ws_name), None)
    if not ws_id:
        raise ExportError(f"Fast.io workspace not found: {ws_name}")

    tp_id = ensure_folder(ws_id, None, "trading-proposals")
    sessions_id = ensure_folder(ws_id, tp_id, "sessions")
    session_id = f"{export_date}-{run_id}"

    existing_session_id = folder_id_by_name(ws_id, sessions_id, session_id)
    existing_watchlist = False
    existing_manifest: dict[str, Any] = {}
    if existing_session_id:
        items = fastio_cmd(
            "files", "list", "--workspace", ws_id, "--folder", existing_session_id
        ).get("nodes", {}).get("items", [])
        for item in items:
            if item.get("name") == "watchlist.txt":
                existing_watchlist = True
            if item.get("name") == "manifest.json" and item.get("id"):
                # manifest download not needed; preserve screeners from upload text update path
                pass
        if existing_watchlist and not overwrite:
            raise ExportError(
                f"Fast.io session already has watchlist.txt at trading-proposals/sessions/{session_id}/; "
                "pass --overwrite to replace"
            )
        session_folder_id = existing_session_id
    else:
        session_folder_id = ensure_folder(ws_id, sessions_id, session_id)

    fastio_cmd(
        "upload",
        "file",
        "--workspace",
        ws_id,
        "--folder",
        session_folder_id,
        str(local_path),
    )

    manifest = {
        "session_id": session_id,
        "run_id": run_id,
        "created_at": export_date,
        "status": "watchlist_exported",
        "files": {
            "watchlist": "watchlist.txt",
            "screeners": [],
        },
        "local_source": str(local_path),
    }

    fastio_cmd(
        "upload",
        "text",
        "--workspace",
        ws_id,
        "--folder",
        session_folder_id,
        "--name",
        "manifest.json",
        json.dumps(manifest, indent=2),
    )

    return {
        "session_path": f"trading-proposals/sessions/{session_id}/",
        "session_id": session_id,
        "manifest_status": manifest["status"],
        "uploaded": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Trading Proposals to TradingView watchlist")
    parser.add_argument("--run-id")
    parser.add_argument("--date", help="Export date YYYY-MM-DD")
    parser.add_argument("--output-dir", default="data/tradingview")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-fastio", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    token = load_env("NOTION_API_TOKEN")
    export_date = args.date or date.today().isoformat()

    runs_ds = search_data_source(token, RUNS_TITLES)
    proposals_ds = search_data_source(token, PROPOSALS_TITLES)
    validate_schema(runs_ds, RUNS_REQUIRED)
    validate_schema(proposals_ds, PROPOSALS_REQUIRED)

    run_id, run_page_id, run_id_source = resolve_run(token, runs_ds["id"], args.run_id)
    proposal_rows = paginate_query(
        token,
        proposals_ds["id"],
        {
            "filter": {"property": "Run", "relation": {"contains": run_page_id}},
            "page_size": 100,
        },
    )
    if not proposal_rows:
        raise ExportError(f"No Trading Proposals linked to run {run_id}")

    proposals = [parse_proposal_row(row) for row in proposal_rows]
    resolved_rows: list[dict[str, Any]] = []
    counts = {"matched": len(proposals), "resolved": 0, "ambiguous": 0, "failed": 0}

    for index, proposal in enumerate(proposals):
        if index > 0:
            time.sleep(1)
        result = resolve_tv_symbol(proposal)
        row = {**proposal, **result}
        resolved_rows.append(row)
        status = result.get("status", "failed")
        if status in counts:
            counts[status] += 1

    watchlist = build_watchlist(resolved_rows)
    output_dir = Path(args.output_dir)
    output_path = output_dir / f"{export_date}-{run_id}.txt"

    if output_path.exists() and not args.dry_run and not args.overwrite:
        raise ExportError(
            f"Output file already exists: {output_path}. Pass --overwrite to replace."
        )

    fastio_result: dict[str, Any] | None = None
    if not args.dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path.write_text(watchlist, encoding="utf-8")
        if not args.no_fastio:
            fastio_result = upload_fastio_session(
                output_path,
                watchlist,
                export_date,
                run_id,
                overwrite=args.overwrite,
            )

    report = {
        "run_id": run_id,
        "run_id_source": run_id_source,
        "run_page_id": run_page_id,
        "export_date": export_date,
        "output_path": str(output_path),
        "dry_run": args.dry_run,
        "counts": counts,
        "rows": resolved_rows,
        "watchlist_tv_ids": [
            row["tv_id"] for row in resolved_rows if row.get("status") == "resolved"
        ],
        "fastio": fastio_result or {"skipped": args.no_fastio or args.dry_run},
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ExportError as exc:
        print(json.dumps({"error": str(exc)}, indent=2), file=sys.stderr)
        raise SystemExit(1) from exc
