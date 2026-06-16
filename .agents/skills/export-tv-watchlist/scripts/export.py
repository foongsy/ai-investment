#!/usr/bin/env python3
"""Export Trading Proposals to TradingView watchlist per export-tv-watchlist skill."""

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


def load_env() -> None:
    for env_path in (Path.cwd() / ".env", Path(__file__).resolve().parents[4] / ".env"):
        if not env_path.is_file():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            if key in os.environ:
                continue
            value = value.strip().strip('"').strip("'")
            if value:
                os.environ[key] = value
        break


def notion_request(method: str, path: str, token: str, body: dict | None = None) -> dict:
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode() if body is not None else None
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
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Notion API {method} {path} failed ({exc.code}): {detail}") from exc


def search_data_source(token: str, titles: tuple[str, ...]) -> dict:
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
            plain = "".join(p.get("plain_text", "") for p in item.get("title", []))
            if plain == title:
                return item
        time.sleep(0.35)
    raise RuntimeError(f"Could not find Notion data source. Tried: {', '.join(titles)}")


def paginate_query(token: str, ds_id: str, body: dict) -> list[dict]:
    results: list[dict] = []
    cursor: str | None = None
    while True:
        payload = dict(body)
        if cursor:
            payload["start_cursor"] = cursor
        data = notion_request("POST", f"/data_sources/{ds_id}/query", token, payload)
        results.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
        if not cursor:
            break
        time.sleep(0.35)
    return results


def plain_text(prop: dict | None) -> str:
    if not prop:
        return ""
    ptype = prop.get("type")
    if ptype == "title":
        parts = prop.get("title") or []
    elif ptype == "rich_text":
        parts = prop.get("rich_text") or []
    else:
        return ""
    return "".join(p.get("plain_text", "") for p in parts).strip()


def select_value(prop: dict | None) -> str:
    if not prop or prop.get("type") != "select":
        return ""
    sel = prop.get("select")
    return (sel or {}).get("name", "") if sel else ""


def relation_ids(prop: dict | None) -> list[str]:
    if not prop or prop.get("type") != "relation":
        return []
    return [r["id"] for r in (prop.get("relation") or [])]


def exchange_from_field(exchange: str) -> str | None:
    upper = exchange.upper()
    for key, val in EXCHANGE_MAP.items():
        if key in upper:
            return val
    return None


def search_type_from_asset(asset_class: str) -> str:
    mapping = {"equity": "stock", "etf": "etf", "crypto": "crypto"}
    return mapping.get(asset_class.lower(), "stock")


def normalize_ticker(market: str, ticker: str) -> str:
    t = ticker.strip()
    if market == "HK":
        t = re.sub(r"\.HK$", "", t, flags=re.I)
        if t.isdigit():
            t = t.lstrip("0") or "0"
    elif market == "JP":
        t = re.sub(r"\.T$", "", t, flags=re.I)
    return t


def build_search_params(proposal: dict) -> dict[str, str]:
    market = proposal["market"]
    ticker = proposal["ticker"]
    exchange = proposal.get("exchange", "")
    asset_class = proposal.get("asset_class", "")
    text = normalize_ticker(market, ticker)
    params: dict[str, str] = {"text": text, "lang": "en", "domain": "production"}
    search_type = search_type_from_asset(asset_class)
    params["search_type"] = search_type

    if market == "HK":
        params["exchange"] = "HKEX"
        params["search_type"] = "stock"
    elif market == "JP":
        params["exchange"] = "TSE"
        params["search_type"] = "stock"
        params["country"] = "JP"
    elif market == "US":
        mapped = exchange_from_field(exchange)
        if mapped:
            params["exchange"] = mapped
        params["country"] = "US"
        params["sort_by_country"] = "US"
    else:
        mapped = exchange_from_field(exchange)
        if mapped:
            params["exchange"] = mapped

    return params


def tv_search(params: dict[str, str]) -> dict:
    query = urllib.parse.urlencode({k: v for k, v in params.items() if v})
    url = f"{TV_SEARCH_URL}?{query}"
    req = urllib.request.Request(url, headers=TV_HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def tv_id_from_hit(hit: dict) -> str:
    prefix = (hit.get("prefix") or "").strip()
    symbol = hit.get("symbol", "")
    if prefix:
        return f"{prefix}:{symbol}"
    exchange = (hit.get("exchange") or "").split()[0].upper()
    return f"{exchange}:{symbol}"


def score_hit(hit: dict, proposal: dict, search_text: str, expected_exchange: str | None) -> int:
    score = 0
    market = proposal["market"]
    asset_class = proposal.get("asset_class", "")
    company = (proposal.get("company_name") or "").lower()
    hit_symbol = (hit.get("symbol") or "").upper()
    hit_prefix = (hit.get("prefix") or "").upper()
    hit_exchange = ((hit.get("exchange") or "").split()[0] or "").upper()
    hit_type = (hit.get("type") or "").lower()
    hit_country = (hit.get("country") or "").upper()
    hit_desc = (hit.get("description") or "").lower()

    if expected_exchange:
        exp = expected_exchange.upper()
        if hit_prefix == exp or hit_exchange == exp:
            score += 10

    if hit_symbol == search_text.upper():
        score += 10

    expected_type = search_type_from_asset(asset_class)
    if expected_type in hit_type or hit_type in expected_type:
        score += 5

    if company and company in hit_desc:
        score += 3

    market_country = {"HK": "HK", "JP": "JP", "US": "US"}.get(market)
    if market_country and hit_country == market_country:
        score += 5

    return score


def resolve_symbol(proposal: dict) -> dict:
    params = build_search_params(proposal)
    search_text = params["text"]
    expected_exchange = params.get("exchange")

    def attempt(text: str) -> tuple[str | None, str]:
        p = dict(params)
        p["text"] = text
        try:
            data = tv_search(p)
        except Exception as exc:
            return None, f"http_error: {exc}"
        symbols = data.get("symbols") or []
        if not symbols:
            return None, "empty"
        scored = []
        for hit in symbols:
            tv_id = tv_id_from_hit(hit)
            sc = score_hit(hit, proposal, search_text, expected_exchange)
            scored.append((sc, tv_id, hit))
        scored.sort(key=lambda x: (-x[0], x[1]))
        best_score, best_id, _ = scored[0]
        if best_score < 10:
            return None, f"low_score:{best_score}"
        if len(scored) > 1 and scored[0][0] - scored[1][0] <= 3:
            return None, f"ambiguous:{best_id}/{scored[1][1]}"
        return best_id, "resolved"

    tv_id, reason = attempt(search_text)
    if tv_id:
        return {"status": "resolved", "tv_id": tv_id}

    company = (proposal.get("company_name") or "").strip()
    if company:
        time.sleep(1)
        tv_id, reason2 = attempt(company)
        if tv_id:
            return {"status": "resolved", "tv_id": tv_id}
        reason = f"{reason}; retry:{reason2}"

    if reason.startswith("ambiguous"):
        return {"status": "ambiguous", "reason": reason}
    return {"status": "failed", "reason": reason}


def build_watchlist(resolved: list[tuple[str, str]]) -> str:
    by_market: dict[str, list[str]] = {m: [] for m in MARKET_ORDER}
    for market, tv_id in resolved:
        key = market if market in by_market else "OTHER"
        by_market[key].append(tv_id)

    lines: list[str] = []
    for market in MARKET_ORDER:
        ids = sorted(set(by_market[market]))
        if not ids:
            continue
        lines.append(SECTION_HEADERS[market])
        lines.extend(ids)
        lines.append("")
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) + ("\n" if lines else "")


def fastio_cmd(*args: str) -> dict:
    token = os.environ.get("FASTIO_API_KEY", "")
    if not token:
        raise RuntimeError("FASTIO_API_KEY missing")
    fastio_bin = os.environ.get("FASTIO_BIN", "npx")
    if fastio_bin == "npx":
        cmd = ["npx", "--yes", "@vividengine/fastio-cli", *args, "--token", token, "--format", "json"]
    else:
        cmd = [fastio_bin, *args, "--token", token, "--format", "json"]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"fastio failed: {result.stderr or result.stdout}")
    data = json.loads(result.stdout)
    # create-folder responses use node.id
    if "id" not in data and data.get("node", {}).get("id"):
        data["id"] = data["node"]["id"]
    return data


def folder_id_by_name(ws_id: str, parent_id: str | None, name: str) -> str | None:
    args = ["files", "list", "--workspace", ws_id]
    if parent_id:
        args += ["--folder", parent_id]
    items = fastio_cmd(*args).get("nodes", {}).get("items", [])
    match = next((n for n in items if n.get("type") == "folder" and n.get("name") == name), None)
    return match["id"] if match else None


def provision_fastio(export_date: str, run_id: str, local_path: Path, dry_run: bool) -> dict:
    ws_name = os.environ.get("FASTIO_WORKSPACE_NAME", "")
    if not ws_name:
        raise RuntimeError("FASTIO_WORKSPACE_NAME missing")

    session_id = f"{export_date}-{run_id}"
    session_path = f"trading-proposals/sessions/{session_id}/"

    if dry_run:
        return {
            "status": "planned",
            "session_path": session_path,
            "session_id": session_id,
        }

    workspaces = fastio_cmd("workspace", "list").get("workspaces", [])
    ws_id = next((w["id"] for w in workspaces if w["name"] == ws_name), None)
    if not ws_id:
        raise RuntimeError(f"Fast.io workspace not found: {ws_name}")

    tp_id = folder_id_by_name(ws_id, None, "trading-proposals")
    if not tp_id:
        tp_id = fastio_cmd("files", "create-folder", "--workspace", ws_id, "trading-proposals")["id"]

    sessions_id = folder_id_by_name(ws_id, tp_id, "sessions")
    if not sessions_id:
        sessions_id = fastio_cmd(
            "files", "create-folder", "--workspace", ws_id, "--parent", tp_id, "sessions"
        )["id"]

    session_folder_id = folder_id_by_name(ws_id, sessions_id, session_id)
    existing_watchlist = False
    existing_screeners: list[str] = []

    if session_folder_id:
        items = fastio_cmd(
            "files", "list", "--workspace", ws_id, "--folder", session_folder_id
        ).get("nodes", {}).get("items", [])
        for item in items:
            name = item.get("name", "")
            if name == "watchlist.txt":
                existing_watchlist = True
            if name.startswith("screener") and name.endswith(".csv"):
                existing_screeners.append(name)
        if existing_watchlist:
            raise RuntimeError(
                f"Fast.io session {session_path} already has watchlist.txt; overwrite not allowed"
            )
    else:
        session_folder_id = fastio_cmd(
            "files",
            "create-folder",
            "--workspace",
            ws_id,
            "--parent",
            sessions_id,
            session_id,
        )["id"]

    watchlist_content = local_path.read_text(encoding="utf-8")
    fastio_cmd(
        "upload",
        "text",
        "--workspace",
        ws_id,
        "--folder",
        session_folder_id,
        "--name",
        "watchlist.txt",
        watchlist_content,
    )

    manifest = {
        "session_id": session_id,
        "run_id": run_id,
        "created_at": export_date,
        "status": "watchlist_exported",
        "files": {"watchlist": "watchlist.txt", "screeners": existing_screeners},
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
        "status": "uploaded",
        "session_path": session_path,
        "session_id": session_id,
        "workspace": ws_name,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Export TV watchlist from Trading Proposals")
    parser.add_argument("--run-id")
    parser.add_argument("--date")
    parser.add_argument("--output-dir", default="data/tradingview")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-fastio", action="store_true")
    args = parser.parse_args()

    load_env()
    token = os.environ.get("NOTION_API_TOKEN")
    if not token:
        print("ERROR: NOTION_API_TOKEN missing", file=sys.stderr)
        return 1

    runs_ds_item = search_data_source(token, RUNS_TITLES)
    proposals_ds_item = search_data_source(token, PROPOSALS_TITLES)
    runs_ds_id = runs_ds_item["id"]
    proposals_ds_id = proposals_ds_item["id"]

    runs_schema = notion_request("GET", f"/data_sources/{runs_ds_id}", token)
    proposals_schema = notion_request("GET", f"/data_sources/{proposals_ds_id}", token)
    for ds, required in (
        (runs_schema, ("Run ID",)),
        (proposals_schema, ("Proposal", "Ticker", "Market", "Run")),
    ):
        missing = [p for p in required if p not in ds.get("properties", {})]
        if missing:
            print(f"ERROR: missing properties: {', '.join(missing)}", file=sys.stderr)
            return 1

    run_id_source = "supplied" if args.run_id else "latest_created"
    if args.run_id:
        run_rows = paginate_query(
            token,
            runs_ds_id,
            {
                "filter": {
                    "property": "Run ID",
                    "title": {"equals": args.run_id},
                }
            },
        )
        if not run_rows:
            print(f"ERROR: run_id not found: {args.run_id}", file=sys.stderr)
            return 1
        if len(run_rows) > 1:
            ids = ", ".join(r["id"] for r in run_rows)
            print(f"ERROR: multiple Research Runs match run_id; page IDs: {ids}", file=sys.stderr)
            return 1
        run_row = run_rows[0]
        run_id = args.run_id
    else:
        run_rows = paginate_query(
            token,
            runs_ds_id,
            {
                "filter": {
                    "property": "Run ID",
                    "title": {"is_not_empty": True},
                },
                "sorts": [{"timestamp": "created_time", "direction": "descending"}],
                "page_size": 1,
            },
        )
        if not run_rows:
            print("ERROR: no Research Runs rows with a Run ID", file=sys.stderr)
            return 1
        run_row = run_rows[0]
        run_id = plain_text(run_row["properties"].get("Run ID"))

    run_page_id = run_row["id"]
    export_date = args.date or date.today().isoformat()
    output_dir = Path(args.output_dir)
    output_path = output_dir / f"{export_date}-{run_id}.txt"

    if output_path.exists() and not args.dry_run:
        print(f"ERROR: output file exists: {output_path}; overwrite not allowed", file=sys.stderr)
        return 1

    proposal_rows = paginate_query(
        token,
        proposals_ds_id,
        {
            "filter": {
                "property": "Run",
                "relation": {"contains": run_page_id},
            }
        },
    )
    if not proposal_rows:
        print(f"ERROR: no Trading Proposals linked to run {run_id}", file=sys.stderr)
        return 1

    proposals = []
    for row in proposal_rows:
        props = row["properties"]
        proposals.append(
            {
                "page_id": row["id"],
                "proposal": plain_text(props.get("Proposal")),
                "ticker": plain_text(props.get("Ticker")),
                "market": select_value(props.get("Market")) or "OTHER",
                "exchange": plain_text(props.get("Exchange")) if "Exchange" in props else "",
                "asset_class": select_value(props.get("Asset Class")) if "Asset Class" in props else "",
                "company_name": plain_text(props.get("Company Name")) if "Company Name" in props else "",
            }
        )

    results = []
    resolved_pairs: list[tuple[str, str]] = []
    counts = {"matched": len(proposals), "resolved": 0, "ambiguous": 0, "failed": 0}

    for i, proposal in enumerate(proposals):
        if i > 0:
            time.sleep(1)
        outcome = resolve_symbol(proposal)
        row_result = {**proposal, **outcome}
        results.append(row_result)
        if outcome["status"] == "resolved":
            counts["resolved"] += 1
            resolved_pairs.append((proposal["market"], outcome["tv_id"]))
        elif outcome["status"] == "ambiguous":
            counts["ambiguous"] += 1
        else:
            counts["failed"] += 1

    watchlist = build_watchlist(resolved_pairs)
    tv_ids_written = sorted({tv for _, tv in resolved_pairs})

    if args.dry_run:
        print(json.dumps({
            "run_id": run_id,
            "run_id_source": run_id_source,
            "run_page_id": run_page_id,
            "output_path": str(output_path),
            "counts": counts,
            "tv_ids": tv_ids_written,
            "watchlist_preview": watchlist,
            "rows": results,
        }, indent=2))
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path.write_text(watchlist, encoding="utf-8")

    fastio_result = None
    if not args.no_fastio:
        fastio_result = provision_fastio(export_date, run_id, output_path, dry_run=False)

    report = {
        "run_id": run_id,
        "run_id_source": run_id_source,
        "run_page_id": run_page_id,
        "output_path": str(output_path),
        "counts": counts,
        "tv_ids": tv_ids_written,
        "fastio": fastio_result or {"status": "skipped"},
        "rows": results,
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
