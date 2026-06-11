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
NOTION_BASE = "https://api.notion.com/v1"
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


class ExportError(Exception):
    pass


def load_env_var(name: str) -> str:
    value = os.environ.get(name)
    if value:
        return value.strip()
    for env_path in (Path.cwd() / ".env", Path(__file__).resolve().parents[4] / ".env"):
        if not env_path.is_file():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith(f"{name}="):
                v = line.split("=", 1)[1].strip().strip('"').strip("'")
                if v:
                    os.environ[name] = v
                    return v
    raise ExportError(f"{name} is missing from environment or .env")


def notion_request(method: str, path: str, token: str, body: dict | None = None) -> dict:
    url = f"{NOTION_BASE}{path}"
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
        raise ExportError(f"Notion API {method} {path} failed ({exc.code}): {detail}") from exc


def search_data_source(token: str, titles: tuple[str, ...]) -> dict:
    for title in titles:
        data = notion_request(
            "POST",
            "/search",
            token,
            {"query": title, "filter": {"property": "object", "value": "data_source"}, "page_size": 20},
        )
        for item in data.get("results", []):
            if item.get("object") != "data_source":
                continue
            plain = "".join(p.get("plain_text", "") for p in item.get("title", []))
            if plain == title:
                return item
        time.sleep(0.35)
    raise ExportError(f"Could not find Notion data source. Tried: {', '.join(titles)}")


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


def plain_text(prop: dict | None) -> str | None:
    if not prop:
        return None
    t = prop.get("type")
    if t == "title":
        parts = prop.get("title") or []
    elif t == "rich_text":
        parts = prop.get("rich_text") or []
    else:
        return None
    text = "".join(p.get("plain_text", "") for p in parts).strip()
    return text or None


def select_name(prop: dict | None) -> str | None:
    if not prop or prop.get("type") != "select":
        return None
    sel = prop.get("select")
    return sel.get("name") if sel else None


def relation_ids(prop: dict | None) -> list[str]:
    if not prop or prop.get("type") != "relation":
        return []
    return [r["id"] for r in (prop.get("relation") or [])]


def validate_schema(ds: dict, required: tuple[str, ...]) -> None:
    props = ds.get("properties", {})
    missing = [n for n in required if n not in props]
    if missing:
        title = "".join(p.get("plain_text", "") for p in ds.get("title", []))
        raise ExportError(f"Data source '{title}' missing properties: {', '.join(missing)}")


def resolve_latest_run(token: str, runs_ds_id: str) -> tuple[str, str]:
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
        raise ExportError("No Research Runs rows with a non-empty Run ID.")
    row = rows[0]
    run_id = plain_text(row["properties"].get("Run ID"))
    if not run_id:
        raise ExportError("Latest Research Runs row has empty Run ID.")
    return run_id, row["id"]


def resolve_run_by_id(token: str, runs_ds_id: str, run_id: str) -> str:
    rows = paginate_query(
        token,
        runs_ds_id,
        {"filter": {"property": "Run ID", "title": {"equals": run_id}}, "page_size": 10},
    )
    if not rows:
        raise ExportError(f"run_id not found: {run_id}")
    if len(rows) > 1:
        ids = ", ".join(r["id"] for r in rows)
        raise ExportError(f"Multiple Research Runs match run_id {run_id}. Page IDs: {ids}")
    return rows[0]["id"]


def fetch_proposals(token: str, proposals_ds_id: str, run_page_id: str) -> list[dict]:
    rows = paginate_query(
        token,
        proposals_ds_id,
        {"filter": {"property": "Run", "relation": {"contains": run_page_id}}, "page_size": 100},
    )
    if not rows:
        raise ExportError("No Trading Proposals linked to this run.")
    proposals = []
    for row in rows:
        props = row["properties"]
        proposals.append(
            {
                "page_id": row["id"],
                "proposal": plain_text(props.get("Proposal")),
                "ticker": (plain_text(props.get("Ticker")) or "").strip(),
                "market": select_name(props.get("Market")) or "OTHER",
                "exchange": plain_text(props.get("Exchange")),
                "asset_class": (select_name(props.get("Asset Class")) or "").lower(),
                "company_name": plain_text(props.get("Company Name")),
            }
        )
    return proposals


def map_exchange(exchange: str | None) -> str | None:
    if not exchange:
        return None
    upper = exchange.upper()
    for key, val in EXCHANGE_MAP.items():
        if key in upper:
            return val
    return None


def search_type(asset_class: str) -> str:
    mapping = {"equity": "stock", "etf": "etf", "crypto": "crypto"}
    return mapping.get(asset_class, "stock")


def normalize_search(proposal: dict) -> tuple[str, dict[str, str]]:
    market = proposal["market"]
    ticker = proposal["ticker"]
    exchange = proposal.get("exchange")
    asset_class = proposal.get("asset_class") or ""
    params: dict[str, str] = {"lang": "en", "search_type": search_type(asset_class), "domain": "production"}

    if market == "HK":
        text = re.sub(r"\.HK$", "", ticker, flags=re.I)
        if text.isdigit():
            text = text.lstrip("0") or "0"
        params["text"] = text
        params["exchange"] = "HKEX"
        params["search_type"] = "stock"
    elif market == "JP":
        text = re.sub(r"\.T$", "", ticker, flags=re.I)
        params["text"] = text
        params["exchange"] = "TSE"
        params["search_type"] = "stock"
        params["country"] = "JP"
        params["sort_by_country"] = "JP"
    elif market == "US":
        params["text"] = ticker
        tv_ex = map_exchange(exchange)
        if tv_ex:
            params["exchange"] = tv_ex
        params["country"] = "US"
        params["sort_by_country"] = "US"
    else:
        params["text"] = ticker
        tv_ex = map_exchange(exchange)
        if tv_ex:
            params["exchange"] = tv_ex

    return params["text"], params


def tv_search(params: dict[str, str]) -> dict:
    query = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{TV_SEARCH_URL}?{query}", headers=TV_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return {"symbols": [], "error": exc.read().decode("utf-8", errors="replace")}


def build_tv_id(hit: dict) -> str:
    prefix = hit.get("prefix") or ""
    symbol = hit.get("symbol") or ""
    if prefix:
        return f"{prefix}:{symbol}"
    exchange = (hit.get("exchange") or "").split()[0].upper()
    return f"{exchange}:{symbol}"


def score_hit(hit: dict, proposal: dict, search_text: str, expected_exchange: str | None) -> int:
    score = 0
    market = proposal["market"]
    asset_class = proposal.get("asset_class") or ""
    company = (proposal.get("company_name") or "").lower()

    hit_prefix = (hit.get("prefix") or "").upper()
    hit_exchange = (hit.get("exchange") or "").split()[0].upper()
    hit_symbol = (hit.get("symbol") or "").upper()
    hit_type = (hit.get("type") or "").lower()
    hit_country = (hit.get("country") or "").upper()
    hit_desc = (hit.get("description") or "").lower()

    if expected_exchange and (hit_prefix == expected_exchange or hit_exchange == expected_exchange):
        score += 10
    if hit_symbol == search_text.upper():
        score += 10

    st = search_type(asset_class)
    type_align = (
        (st == "stock" and hit_type in ("stock", "dr"))
        or (st == "etf" and hit_type == "etf")
        or (st == "crypto" and hit_type == "crypto")
    )
    if type_align:
        score += 5

    if company and company in hit_desc:
        score += 3

    market_country = {"HK": "HK", "JP": "JP", "US": "US"}.get(market)
    if market_country and hit_country == market_country:
        score += 5

    return score


def resolve_tv_symbol(proposal: dict) -> dict:
    search_text, params = normalize_search(proposal)
    expected_exchange = params.get("exchange")

    def attempt(text: str) -> dict:
        p = dict(params)
        p["text"] = text
        data = tv_search(p)
        symbols = data.get("symbols") or []
        if not symbols:
            return {"status": "empty", "symbols": []}

        scored = []
        for hit in symbols:
            tv_id = build_tv_id(hit)
            score = score_hit(hit, proposal, text, expected_exchange)
            scored.append((score, tv_id, hit))
        scored.sort(key=lambda x: (-x[0], x[1]))

        best_score, best_id, _ = scored[0]
        second_score = scored[1][0] if len(scored) > 1 else -1

        if best_score < 10:
            return {"status": "ambiguous", "reason": f"best score {best_score} < 10", "symbols": scored[:3]}
        if len(scored) > 1 and abs(best_score - second_score) <= 3:
            return {
                "status": "ambiguous",
                "reason": f"top scores tied within 3 ({best_score} vs {second_score})",
                "symbols": scored[:3],
            }
        return {"status": "resolved", "tv_id": best_id, "score": best_score}

    result = attempt(search_text)
    company = (proposal.get("company_name") or "").strip()
    if result["status"] == "empty" and company:
        time.sleep(1)
        result = attempt(company)

    if result["status"] == "resolved":
        return result
    if result["status"] == "ambiguous":
        return result
    return {"status": "failed", "reason": "no symbols returned"}


def build_watchlist(resolved: list[dict]) -> str:
    by_market: dict[str, list[str]] = {m: [] for m in MARKET_ORDER}
    for row in resolved:
        if row.get("tv_id"):
            market = row["market"] if row["market"] in by_market else "OTHER"
            by_market[market].append(row["tv_id"])

    lines: list[str] = []
    for market in MARKET_ORDER:
        ids = sorted(set(by_market[market]))
        if not ids:
            continue
        lines.append(SECTION_HEADERS[market])
        lines.extend(ids)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n" if lines else ""


def resolve_fastio_bin() -> str:
    import shutil

    if shutil.which("fastio"):
        return "fastio"
    repo_fastio = Path(__file__).resolve().parents[4] / "node_modules" / ".bin" / "fastio"
    if repo_fastio.is_file():
        return str(repo_fastio)
    raise ExportError(
        "fastio CLI not found. Install with: npm install -g @vividengine/fastio-cli "
        "or use --no-fastio"
    )


def fastio_cmd(*args: str) -> dict:
    token = load_env_var("FASTIO_API_KEY")
    fastio_bin = resolve_fastio_bin()
    result = subprocess.run(
        [str(fastio_bin), *args, "--token", token, "--format", "json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise ExportError(f"fastio {' '.join(args)} failed: {result.stderr or result.stdout}")
    return json.loads(result.stdout)


def list_items(ws_id: str, parent_id: str | None) -> list[dict]:
    args = ["files", "list", "--workspace", ws_id]
    if parent_id:
        args.extend(["--folder", parent_id])
    data = fastio_cmd(*args)
    return data.get("nodes", {}).get("items", data.get("files", data.get("items", [])))


def find_folder(ws_id: str, parent_id: str | None, name: str) -> dict | None:
    for item in list_items(ws_id, parent_id):
        if item.get("name") == name and item.get("type") == "folder":
            return item
    return None


def ensure_folder(ws_id: str, parent_id: str | None, name: str) -> str:
    existing = find_folder(ws_id, parent_id, name)
    if existing:
        return existing["id"]
    args = ["files", "create-folder", "--workspace", ws_id, name]
    if parent_id:
        args.extend(["--parent", parent_id])
    data = fastio_cmd(*args)
    node = data.get("node") or data.get("folder") or data
    return node["id"]


def list_session_files(ws_id: str, session_folder_id: str) -> list[dict]:
    return list_items(ws_id, session_folder_id)


def upload_text(ws_id: str, folder_id: str, name: str, text: str) -> dict:
    return fastio_cmd(
        "upload",
        "text",
        "--workspace",
        ws_id,
        "--folder",
        folder_id,
        "--name",
        name,
        text,
    )


def provision_fastio(
    export_date: str,
    run_id: str,
    local_path: Path,
    content: str,
    force: bool = False,
) -> dict:
    ws_name = load_env_var("FASTIO_WORKSPACE_NAME")
    workspaces = fastio_cmd("workspace", "list")
    ws_id = None
    for ws in workspaces.get("workspaces", workspaces.get("items", [])):
        if ws.get("name") == ws_name:
            ws_id = ws["id"]
            break
    if not ws_id:
        raise ExportError(f"Fast.io workspace not found: {ws_name}")

    tp_id = ensure_folder(ws_id, None, "trading-proposals")
    sessions_id = ensure_folder(ws_id, tp_id, "sessions")
    session_name = f"{export_date}-{run_id}"

    existing = find_folder(ws_id, sessions_id, session_name)
    if existing:
        session_folder_id = existing["id"]
        files = list_session_files(ws_id, session_folder_id)
        if any(f.get("name") == "watchlist.txt" for f in files) and not force:
            raise ExportError(
                f"Fast.io session {session_name} already has watchlist.txt. "
                "Use --force to overwrite."
            )
    else:
        data = fastio_cmd(
            "files", "create-folder", "--workspace", ws_id, "--parent", sessions_id, session_name
        )
        node = data.get("node") or data.get("folder") or data
        session_folder_id = node["id"]

    upload_text(ws_id, session_folder_id, "watchlist.txt", content)

    session_path = f"trading-proposals/sessions/{session_name}/"
    screeners: list[str] = []
    for f in list_session_files(ws_id, session_folder_id):
        fname = f.get("name", "")
        if fname.startswith("screener") and fname.endswith(".csv"):
            screeners.append(fname)

    manifest = {
        "session_id": session_name,
        "run_id": run_id,
        "created_at": export_date,
        "status": "watchlist_exported",
        "files": {"watchlist": "watchlist.txt", "screeners": screeners},
        "local_source": str(local_path),
    }
    upload_text(ws_id, session_folder_id, "manifest.json", json.dumps(manifest, indent=2) + "\n")

    return {"session_path": session_path, "session_id": session_name, "status": "watchlist_exported"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Trading Proposals to TV watchlist")
    parser.add_argument("--run-id", help="Research run ID (default: latest created)")
    parser.add_argument("--date", help="Export date YYYY-MM-DD (default: today)")
    parser.add_argument("--output-dir", default="data/tradingview")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-fastio", action="store_true")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    args = parser.parse_args()

    token = load_env_var("NOTION_API_TOKEN")
    export_date = args.date or date.today().isoformat()
    output_dir = Path(args.output_dir)
    run_id_source = "supplied" if args.run_id else "latest_created"

    runs_ds = search_data_source(token, RUNS_TITLES)
    proposals_ds = search_data_source(token, PROPOSALS_TITLES)
    validate_schema(runs_ds, ("Run ID",))
    validate_schema(proposals_ds, ("Proposal", "Ticker", "Market", "Run"))

    if args.run_id:
        run_id = args.run_id
        run_page_id = resolve_run_by_id(token, runs_ds["id"], run_id)
    else:
        run_id, run_page_id = resolve_latest_run(token, runs_ds["id"])

    proposals = fetch_proposals(token, proposals_ds["id"], run_page_id)
    output_path = output_dir / f"{export_date}-{run_id}.txt"

    if output_path.exists() and not args.dry_run and not args.force:
        raise ExportError(f"Output file exists: {output_path}. Use --force to overwrite.")

    resolved_rows: list[dict] = []
    counts = {"resolved": 0, "ambiguous": 0, "failed": 0}

    for i, prop in enumerate(proposals):
        if i > 0:
            time.sleep(1)
        result = resolve_tv_symbol(prop)
        row = {**prop, **result}
        resolved_rows.append(row)
        status = result.get("status", "failed")
        if status == "resolved":
            counts["resolved"] += 1
        elif status == "ambiguous":
            counts["ambiguous"] += 1
        else:
            counts["failed"] += 1

    content = build_watchlist(resolved_rows)
    tv_ids = [r["tv_id"] for r in resolved_rows if r.get("tv_id")]

    fastio_result = None
    if not args.dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        if not args.no_fastio:
            fastio_result = provision_fastio(export_date, run_id, output_path, content, args.force)

    report = {
        "run_id": run_id,
        "run_id_source": run_id_source,
        "run_page_id": run_page_id,
        "export_date": export_date,
        "output_path": str(output_path),
        "dry_run": args.dry_run,
        "proposals_matched": len(proposals),
        "resolved": counts["resolved"],
        "ambiguous": counts["ambiguous"],
        "failed": counts["failed"],
        "tv_ids": tv_ids,
        "fastio": fastio_result,
        "rows": [
            {
                "proposal": r.get("proposal"),
                "ticker": r.get("ticker"),
                "market": r.get("market"),
                "tv_id": r.get("tv_id"),
                "status": r.get("status"),
                "reason": r.get("reason"),
                "page_id": r.get("page_id"),
            }
            for r in resolved_rows
        ],
        "watchlist_preview": content if args.dry_run else None,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ExportError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        sys.exit(1)
