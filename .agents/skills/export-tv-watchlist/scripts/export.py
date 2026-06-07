#!/usr/bin/env python3
"""Export Trading Proposals for one Research Run to a TradingView watchlist."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

# Reuse Notion helpers from evaluate-portfolio-guardrails.
_GUARDRAILS_SCRIPTS = (
    Path(__file__).resolve().parents[2] / "evaluate-portfolio-guardrails" / "scripts"
)
sys.path.insert(0, str(_GUARDRAILS_SCRIPTS))

from notion_fetch import (  # noqa: E402
    NotionError,
    _paginate_query,
    _plain_text,
    _relation_ids,
    _search_data_source,
    _select,
    load_notion_token,
)

RUNS_TITLES = ("Research Runs",)
PROPOSALS_TITLES = ("Trading Proposals", "Trade Proposals", "Proposals")

RUNS_REQUIRED = ("Run ID",)
PROPOSALS_REQUIRED = ("Proposal", "Ticker", "Market", "Run")

TV_SEARCH_URL = "https://symbol-search.tradingview.com/symbol_search/v3/"
TV_HEADERS = {
    "Origin": "https://www.tradingview.com",
    "Referer": "https://www.tradingview.com/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}

MARKET_SECTION_ORDER = ("HK", "JP", "US", "OTHER")
SECTION_HEADERS = {
    "HK": "###HK",
    "JP": "###JP",
    "US": "###US",
    "OTHER": "###OTHER",
}


def _validate_schema(data_source: dict[str, Any], required: tuple[str, ...]) -> None:
    props = data_source.get("properties", {})
    missing = [name for name in required if name not in props]
    if missing:
        title = "".join(part.get("plain_text", "") for part in data_source.get("title", []))
        raise NotionError(
            f"Data source '{title}' is missing required properties: {', '.join(missing)}"
        )


def _title_text(prop: dict[str, Any] | None) -> str | None:
    if not prop or prop.get("type") != "title":
        return None
    parts = prop.get("title") or []
    text = "".join(part.get("plain_text", "") for part in parts).strip()
    return text or None


def load_fastio_env() -> tuple[str, str]:
    api_key = os.environ.get("FASTIO_API_KEY")
    workspace = os.environ.get("FASTIO_WORKSPACE_NAME")
    if not api_key or not workspace:
        env_path = Path.cwd() / ".env"
        if not env_path.is_file():
            repo_env = Path(__file__).resolve().parents[4] / ".env"
            if repo_env.is_file():
                env_path = repo_env
        if env_path.is_file():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                value = value.strip().strip('"').strip("'")
                if key == "FASTIO_API_KEY" and not api_key:
                    api_key = value
                    os.environ["FASTIO_API_KEY"] = value
                elif key == "FASTIO_WORKSPACE_NAME" and not workspace:
                    workspace = value
                    os.environ["FASTIO_WORKSPACE_NAME"] = value
    if not api_key:
        raise NotionError("FASTIO_API_KEY is missing.")
    if not workspace:
        raise NotionError("FASTIO_WORKSPACE_NAME is missing.")
    return api_key, workspace


def fastio_cmd(api_key: str, *args: str) -> dict[str, Any]:
    cmd = ["npx", "--yes", "@vividengine/fastio-cli", *args, "--token", api_key, "--format", "json"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise NotionError(
            f"fastio {' '.join(args)} failed ({result.returncode}): {result.stderr or result.stdout}"
        )
    return json.loads(result.stdout)


def resolve_latest_run(token: str, runs_ds_id: str) -> tuple[str, str]:
    rows = _paginate_query(
        token,
        runs_ds_id,
        {
            "filter": {"property": "Run ID", "title": {"is_not_empty": True}},
            "sorts": [{"timestamp": "created_time", "direction": "descending"}],
            "page_size": 1,
        },
    )
    if not rows:
        raise NotionError("No Research Runs rows with a non-empty Run ID.")
    row = rows[0]
    run_id = _title_text(row.get("properties", {}).get("Run ID"))
    if not run_id:
        raise NotionError("Latest Research Runs row has an empty Run ID.")
    return run_id, row["id"]


def resolve_run_by_id(token: str, runs_ds_id: str, run_id: str) -> str:
    rows = _paginate_query(
        token,
        runs_ds_id,
        {
            "filter": {"property": "Run ID", "title": {"equals": run_id}},
            "page_size": 10,
        },
    )
    if not rows:
        raise NotionError(f"run_id not found: {run_id}")
    if len(rows) > 1:
        ids = ", ".join(row["id"] for row in rows)
        raise NotionError(f"Multiple Research Runs rows match run_id {run_id}: {ids}")
    return rows[0]["id"]


def fetch_proposals_for_run(
    token: str, proposals_ds_id: str, run_page_id: str
) -> list[dict[str, Any]]:
    rows = _paginate_query(
        token,
        proposals_ds_id,
        {
            "filter": {"property": "Run", "relation": {"contains": run_page_id}},
            "page_size": 100,
        },
    )
    proposals: list[dict[str, Any]] = []
    for row in rows:
        props = row.get("properties", {})
        proposals.append(
            {
                "page_id": row["id"],
                "proposal": _title_text(props.get("Proposal")),
                "ticker": (_plain_text(props.get("Ticker")) or "").strip(),
                "market": _select(props.get("Market")),
                "exchange": _plain_text(props.get("Exchange")),
                "asset_class": (_select(props.get("Asset Class")) or "").lower() or None,
                "company_name": _plain_text(props.get("Company Name")),
            }
        )
    return proposals


def exchange_from_text(exchange: str | None) -> str | None:
    if not exchange:
        return None
    upper = exchange.upper()
    mapping = [
        ("NASDAQ", "NASDAQ"),
        ("NYSE", "NYSE"),
        ("AMEX", "AMEX"),
        ("HKEX", "HKEX"),
        ("HONG KONG", "HKEX"),
        ("TSE", "TSE"),
        ("TOKYO", "TSE"),
    ]
    for needle, tv_exchange in mapping:
        if needle in upper:
            return tv_exchange
    return None


def search_type_from_asset_class(asset_class: str | None) -> str:
    mapping = {"equity": "stock", "etf": "etf", "crypto": "crypto"}
    return mapping.get((asset_class or "").lower(), "stock")


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


def build_search_params(proposal: dict[str, Any]) -> dict[str, str]:
    market = (proposal.get("market") or "OTHER").upper()
    ticker = proposal.get("ticker") or ""
    exchange = proposal.get("exchange")
    asset_class = proposal.get("asset_class")
    search_type = search_type_from_asset_class(asset_class)
    text = normalize_search_text(ticker, market)

    params: dict[str, str] = {
        "text": text,
        "lang": "en",
        "search_type": search_type,
        "domain": "production",
    }

    if market == "HK":
        params["exchange"] = "HKEX"
        params["search_type"] = "stock"
    elif market == "JP":
        params["exchange"] = "TSE"
        params["search_type"] = "stock"
        params["country"] = "JP"
        params["sort_by_country"] = "JP"
    elif market == "US":
        tv_exchange = exchange_from_text(exchange)
        if tv_exchange:
            params["exchange"] = tv_exchange
        params["country"] = "US"
        params["sort_by_country"] = "US"
    else:
        tv_exchange = exchange_from_text(exchange)
        if tv_exchange:
            params["exchange"] = tv_exchange

    return params


def tv_search(params: dict[str, str]) -> dict[str, Any]:
    query = urllib.parse.urlencode({k: v for k, v in params.items() if v})
    req = urllib.request.Request(f"{TV_SEARCH_URL}?{query}", headers=TV_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise NotionError(f"TradingView search failed ({exc.code}): {detail}") from exc


def symbol_to_tv_id(symbol: dict[str, Any]) -> str:
    prefix = (symbol.get("prefix") or "").strip()
    sym = symbol.get("symbol") or ""
    if prefix:
        return f"{prefix}:{sym}"
    exchange = symbol.get("exchange") or ""
    token = exchange.split()[0].upper() if exchange else "UNKNOWN"
    return f"{token}:{sym}"


def expected_exchange(market: str | None, exchange: str | None) -> str | None:
    market = (market or "").upper()
    if market == "HK":
        return "HKEX"
    if market == "JP":
        return "TSE"
    if market == "US":
        return exchange_from_text(exchange)
    return exchange_from_text(exchange)


def score_hit(
    hit: dict[str, Any],
    *,
    market: str | None,
    search_text: str,
    asset_class: str | None,
    company_name: str | None,
    expected_tv_exchange: str | None,
) -> int:
    score = 0
    hit_prefix = (hit.get("prefix") or "").upper()
    hit_exchange = (hit.get("exchange") or "").split()[0].upper()
    hit_symbol = (hit.get("symbol") or "").upper()
    hit_type = (hit.get("type") or "").lower()
    hit_country = (hit.get("country") or "").upper()
    hit_desc = (hit.get("description") or "").lower()

    if expected_tv_exchange:
        expected = expected_tv_exchange.upper()
        if hit_prefix == expected or hit_exchange == expected:
            score += 10

    if hit_symbol == search_text.upper():
        score += 10

    search_type = search_type_from_asset_class(asset_class)
    type_map = {"stock": "stock", "etf": "fund", "crypto": "bitcoin"}
    if hit_type and search_type in type_map and type_map[search_type] in hit_type:
        score += 5
    elif hit_type and search_type in hit_type:
        score += 5

    if company_name and company_name.lower() in hit_desc:
        score += 3

    market_country = {"HK": "HK", "JP": "JP", "US": "US"}.get((market or "").upper())
    if market_country and hit_country == market_country:
        score += 5

    return score


def resolve_tv_symbol(proposal: dict[str, Any]) -> tuple[str | None, str]:
    market = proposal.get("market")
    ticker = proposal.get("ticker") or ""
    company_name = proposal.get("company_name")
    asset_class = proposal.get("asset_class")
    exchange = proposal.get("exchange")
    search_text = normalize_search_text(ticker, market)
    expected = expected_exchange(market, exchange)

    def pick(params: dict[str, str]) -> tuple[str | None, str]:
        try:
            data = tv_search(params)
        except NotionError as exc:
            return None, str(exc)

        symbols = data.get("symbols") or []
        if not symbols:
            return None, "no symbols returned"

        scored = []
        for hit in symbols:
            score = score_hit(
                hit,
                market=market,
                search_text=search_text,
                asset_class=asset_class,
                company_name=company_name,
                expected_tv_exchange=expected,
            )
            scored.append((score, symbol_to_tv_id(hit)))

        scored.sort(key=lambda item: item[0], reverse=True)
        best_score, best_id = scored[0]
        second_score = scored[1][0] if len(scored) > 1 else -999

        if best_score < 10:
            return None, f"ambiguous (best score {best_score})"
        if abs(best_score - second_score) <= 3:
            return None, f"ambiguous (tied scores {best_score}/{second_score})"
        return best_id, "resolved"

    params = build_search_params(proposal)
    tv_id, reason = pick(params)
    if tv_id:
        return tv_id, reason

    if company_name:
        retry_params = dict(params)
        retry_params["text"] = company_name
        time.sleep(1)
        tv_id, retry_reason = pick(retry_params)
        if tv_id:
            return tv_id, "resolved (company name retry)"
        reason = retry_reason

    return None, reason if reason != "resolved" else "failed"


def build_watchlist(resolved_rows: list[dict[str, Any]]) -> str:
    by_market: dict[str, list[str]] = {market: [] for market in MARKET_SECTION_ORDER}
    for row in resolved_rows:
        tv_id = row.get("tv_id")
        market = (row.get("market") or "OTHER").upper()
        if not tv_id:
            continue
        if market not in by_market:
            market = "OTHER"
        by_market[market].append(tv_id)

    lines: list[str] = []
    for market in MARKET_SECTION_ORDER:
        symbols = sorted(set(by_market[market]))
        if not symbols:
            continue
        lines.append(SECTION_HEADERS[market])
        lines.extend(symbols)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def folder_id_by_name(
    api_key: str, workspace_id: str, parent_id: str | None, name: str
) -> str | None:
    args = ["files", "list", "--workspace", workspace_id]
    if parent_id:
        args += ["--folder", parent_id]
    data = fastio_cmd(api_key, *args)
    items = data.get("nodes", {}).get("items", [])
    match = next(
        (item for item in items if item.get("type") == "folder" and item.get("name") == name),
        None,
    )
    return match["id"] if match else None


def ensure_folder(
    api_key: str, workspace_id: str, parent_id: str | None, name: str
) -> str:
    existing = folder_id_by_name(api_key, workspace_id, parent_id, name)
    if existing:
        return existing
    args = ["files", "create-folder", "--workspace", workspace_id, name]
    if parent_id:
        args[3:3] = ["--parent", parent_id]
    data = fastio_cmd(api_key, *args)
    folder_id = data.get("id") or data.get("folder_id")
    if not folder_id:
        folder_id = folder_id_by_name(api_key, workspace_id, parent_id, name)
    if not folder_id:
        raise NotionError(f"Failed to create Fast.io folder: {name}")
    return folder_id


def session_has_watchlist(api_key: str, workspace_id: str, session_folder_id: str) -> bool:
    data = fastio_cmd(api_key, "files", "list", "--workspace", workspace_id, "--folder", session_folder_id)
    items = data.get("nodes", {}).get("items", [])
    return any(item.get("name") == "watchlist.txt" for item in items)


def read_manifest_screeners(
    api_key: str, workspace_id: str, session_folder_id: str
) -> list[str]:
    data = fastio_cmd(api_key, "files", "list", "--workspace", workspace_id, "--folder", session_folder_id)
    items = data.get("nodes", {}).get("items", [])
    manifest = next((item for item in items if item.get("name") == "manifest.json"), None)
    if not manifest:
        return []
    with tempfile.TemporaryDirectory() as tmpdir:
        fastio_cmd(
            api_key,
            "download",
            "file",
            "--workspace",
            workspace_id,
            manifest["id"],
            "--output",
            tmpdir,
        )
        manifest_path = Path(tmpdir) / "manifest.json"
        if not manifest_path.is_file():
            return []
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        screeners = payload.get("files", {}).get("screeners") or []
        return [name for name in screeners if isinstance(name, str)]


def provision_fastio_session(
    *,
    api_key: str,
    workspace_name: str,
    session_id: str,
    run_id: str,
    export_date: str,
    local_path: Path,
    watchlist_content: str,
    dry_run: bool,
) -> dict[str, Any]:
    session_path = f"trading-proposals/sessions/{session_id}/"
    result: dict[str, Any] = {
        "session_path": session_path,
        "status": "skipped",
    }
    if dry_run:
        result["status"] = "planned"
        return result

    workspaces = fastio_cmd(api_key, "workspace", "list").get("workspaces", [])
    workspace = next((ws for ws in workspaces if ws.get("name") == workspace_name), None)
    if not workspace:
        raise NotionError(f"Fast.io workspace not found: {workspace_name}")
    ws_id = workspace["id"]

    tp_id = ensure_folder(api_key, ws_id, None, "trading-proposals")
    sessions_id = ensure_folder(api_key, ws_id, tp_id, "sessions")

    existing_session_id = folder_id_by_name(api_key, ws_id, sessions_id, session_id)
    if existing_session_id and session_has_watchlist(api_key, ws_id, existing_session_id):
        raise NotionError(
            f"Fast.io session already has watchlist.txt: {session_path}. "
            "Re-run with confirmation to overwrite."
        )

    session_folder_id = existing_session_id or ensure_folder(
        api_key, ws_id, sessions_id, session_id
    )

    fastio_cmd(
        api_key,
        "upload",
        "file",
        "--workspace",
        ws_id,
        "--folder",
        session_folder_id,
        str(local_path),
    )

    screeners = read_manifest_screeners(api_key, ws_id, session_folder_id)
    manifest = {
        "session_id": session_id,
        "run_id": run_id,
        "created_at": export_date,
        "status": "watchlist_exported",
        "files": {
            "watchlist": "watchlist.txt",
            "screeners": screeners,
        },
        "local_source": str(local_path),
    }
    fastio_cmd(
        api_key,
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

    result["status"] = "uploaded"
    result["workspace_id"] = ws_id
    result["session_folder_id"] = session_folder_id
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Trading Proposals to TradingView watchlist")
    parser.add_argument("--run-id", help="Research run id (default: latest created run)")
    parser.add_argument("--date", help="Export date YYYY-MM-DD (default: local today)")
    parser.add_argument("--output-dir", default="data/tradingview", help="Output directory")
    parser.add_argument("--dry-run", action="store_true", help="Preview only; no file or Fast.io writes")
    parser.add_argument("--no-fastio", action="store_true", help="Skip Fast.io provisioning")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing local watchlist or Fast.io watchlist.txt",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    export_date = args.date or date.today().isoformat()
    output_dir = Path(args.output_dir)
    token = load_notion_token()

    runs_ds = _search_data_source(token, RUNS_TITLES)
    proposals_ds = _search_data_source(token, PROPOSALS_TITLES)
    _validate_schema(runs_ds, RUNS_REQUIRED)
    _validate_schema(proposals_ds, PROPOSALS_REQUIRED)

    run_id_source = "supplied" if args.run_id else "latest_created"
    if args.run_id:
        run_page_id = resolve_run_by_id(token, runs_ds["id"], args.run_id)
        run_id = args.run_id
    else:
        run_id, run_page_id = resolve_latest_run(token, runs_ds["id"])

    proposals = fetch_proposals_for_run(token, proposals_ds["id"], run_page_id)
    if not proposals:
        raise NotionError(f"No Trading Proposals linked to run {run_id}.")

    resolved_rows: list[dict[str, Any]] = []
    counts = {"matched": len(proposals), "resolved": 0, "ambiguous": 0, "failed": 0}

    for index, proposal in enumerate(proposals):
        if index > 0:
            time.sleep(1)
        tv_id, reason = resolve_tv_symbol(proposal)
        row = {**proposal, "tv_id": tv_id, "resolve_reason": reason}
        resolved_rows.append(row)
        if tv_id:
            counts["resolved"] += 1
        elif "ambiguous" in reason:
            counts["ambiguous"] += 1
        else:
            counts["failed"] += 1

    watchlist_content = build_watchlist(resolved_rows)
    output_path = output_dir / f"{export_date}-{run_id}.txt"

    if output_path.exists() and not args.dry_run and not args.force:
        raise NotionError(
            f"Output file already exists: {output_path}. Use --force to overwrite."
        )

    fastio_result: dict[str, Any] | None = None
    if not args.dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path.write_text(watchlist_content, encoding="utf-8")

        if not args.no_fastio:
            api_key, workspace_name = load_fastio_env()
            session_id = f"{export_date}-{run_id}"
            fastio_result = provision_fastio_session(
                api_key=api_key,
                workspace_name=workspace_name,
                session_id=session_id,
                run_id=run_id,
                export_date=export_date,
                local_path=output_path,
                watchlist_content=watchlist_content,
                dry_run=False,
            )

    report = {
        "run_id": run_id,
        "run_id_source": run_id_source,
        "run_page_id": run_page_id,
        "export_date": export_date,
        "output_path": str(output_path),
        "dry_run": args.dry_run,
        "counts": counts,
        "fastio": fastio_result,
        "rows": resolved_rows,
        "watchlist_tv_ids": sorted(
            {row["tv_id"] for row in resolved_rows if row.get("tv_id")}
        ),
        "watchlist_content": watchlist_content,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except NotionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
