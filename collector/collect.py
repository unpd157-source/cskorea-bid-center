#!/usr/bin/env python3
"""Collect and normalize KONEPS bid notices into a static JSON file.

The collector deliberately does not apply institution or keyword filters.
Those rules belong to the next implementation stage.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

KST = timezone(timedelta(hours=9))
OPERATIONS = {
    "services": "getBidPblancListInfoServc",
    "goods": "getBidPblancListInfoThng",
    "construction": "getBidPblancListInfoCnstwk",
}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def first(item: dict[str, Any], *names: str) -> Any:
    for name in names:
        value = item.get(name)
        if value not in (None, ""):
            return value
    return None


def normalize_item(item: dict[str, Any], category: str) -> dict[str, Any]:
    notice_no = str(first(item, "bidNtceNo") or "").strip()
    notice_order = str(first(item, "bidNtceOrd") or "00").strip()
    return {
        "id": f"{notice_no}-{notice_order}",
        "noticeNo": notice_no,
        "noticeOrder": notice_order,
        "category": category,
        "title": first(item, "bidNtceNm"),
        "noticeInstitution": first(item, "ntceInsttNm"),
        "demandInstitution": first(item, "dminsttNm"),
        "publishedAt": first(item, "bidNtceDt"),
        "closedAt": first(item, "bidClseDt"),
        "estimatedPrice": first(item, "presmptPrce"),
        "detailUrl": first(item, "bidNtceDtlUrl", "bidNtceUrl"),
        "region": first(
            item,
            "prtcptPsblRgnNm",
            "bidPrtcptPsblRgnNm",
            "prtcptPsblRgn",
            "rgnNm",
        ),
        "raw": item,
    }


def extract_response(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    response = payload.get("response", payload)
    header = response.get("header", {})
    result_code = str(header.get("resultCode", "00"))
    if result_code not in {"00", "0"}:
        message = header.get("resultMsg", "Unknown API error")
        raise RuntimeError(f"KONEPS API error {result_code}: {message}")

    body = response.get("body") or {}
    items_node = body.get("items") or []
    if isinstance(items_node, dict):
        items = items_node.get("item") or []
    else:
        items = items_node
    if isinstance(items, dict):
        items = [items]
    if not isinstance(items, list):
        items = []
    return items, int(body.get("totalCount") or len(items))


def request_page(
    base_url: str,
    operation: str,
    service_key: str,
    page_no: int,
    page_size: int,
    begin: datetime,
    end: datetime,
    timeout: int,
) -> dict[str, Any]:
    params = {
        "serviceKey": service_key,
        "pageNo": page_no,
        "numOfRows": page_size,
        "type": "json",
        "inqryDiv": "1",
        "inqryBgnDt": begin.strftime("%Y%m%d%H%M"),
        "inqryEndDt": end.strftime("%Y%m%d%H%M"),
    }
    url = f"{base_url.rstrip('/')}/{operation}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": "CS-KOREA-Bid-Center/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} from {operation}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error from {operation}: {exc.reason}") from exc


def collect_live(config: dict[str, Any], service_key: str) -> Iterable[dict[str, Any]]:
    api = config["api"]
    end = datetime.now(KST)
    begin = end - timedelta(hours=int(api["lookback_hours"]))
    page_size = int(api["page_size"])

    for category, operation in OPERATIONS.items():
        if not config["categories"].get(category, False):
            continue
        page_no = 1
        received = 0
        while True:
            payload = request_page(
                api["base_url"], operation, service_key, page_no, page_size,
                begin, end, int(api["timeout_seconds"]),
            )
            items, total_count = extract_response(payload)
            for item in items:
                yield normalize_item(item, category)
            received += len(items)
            if not items or received >= total_count:
                break
            page_no += 1
            time.sleep(0.15)


def collect_mock(mock_dir: Path, config: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for category in OPERATIONS:
        if not config["categories"].get(category, False):
            continue
        payload = load_json(mock_dir / f"{category}.json")
        items, _ = extract_response(payload)
        for item in items:
            yield normalize_item(item, category)


def deduplicate(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}
    for item in items:
        if item["noticeNo"]:
            unique[item["id"]] = item
    return sorted(
        unique.values(),
        key=lambda item: item.get("publishedAt") or "",
        reverse=True,
    )


def apply_filters(items: Iterable[dict[str, Any]], config: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Apply user-editable institution, keyword and nationwide region rules."""
    rules = config.get("filters", {})
    keywords = [str(value).casefold() for value in rules.get("keywords", []) if str(value).strip()]
    excludes = [str(value).casefold() for value in rules.get("exclude_keywords", []) if str(value).strip()]
    groups = [group for group in rules.get("institution_groups", []) if group.get("enabled", False)]
    nationwide = rules.get("nationwide", {})
    allowed_regions = [str(value).casefold() for value in nationwide.get("allowed_regions", [])]
    counts: dict[str, int] = {group["id"]: 0 for group in groups}
    counts["nationwide"] = 0
    matched: list[dict[str, Any]] = []

    for item in items:
        title = str(item.get("title") or "")
        title_folded = title.casefold()
        if keywords and not any(word in title_folded for word in keywords):
            continue
        if excludes and any(word in title_folded for word in excludes):
            continue

        institution_values = list(filter(None, [
            str(item.get("noticeInstitution") or "").strip(),
            str(item.get("demandInstitution") or "").strip(),
        ]))
        institutions = " ".join(institution_values)
        institution_folded = institutions.casefold()
        institution_exact = {value.casefold() for value in institution_values}
        labels: list[str] = []
        group_ids: list[str] = []

        for group in groups:
            exact_names = [str(value).casefold() for value in group.get("institution_names", [])]
            contains = [str(value).casefold() for value in group.get("institution_contains", [])]
            exact_match = any(name and name in institution_exact for name in exact_names)
            contains_match = any(token and token in institution_folded for token in contains)
            if exact_match or contains_match:
                group_ids.append(group["id"])
                labels.append(group["label"])
                counts[group["id"]] += 1

        if not group_ids and nationwide.get("enabled", False):
            region = str(item.get("region") or "").casefold()
            region_ok = (
                (region and any(value in region for value in allowed_regions))
                or (not region and nationwide.get("allow_unknown_region", False))
            )
            if region_ok:
                group_ids.append("nationwide")
                labels.append(nationwide.get("label", "전국"))
                counts["nationwide"] += 1

        if group_ids:
            enriched = dict(item)
            enriched["matches"] = {"groupIds": group_ids, "labels": labels}
            matched.append(enriched)

    return matched, counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("config.json"))
    parser.add_argument("--output", type=Path, default=Path("public/data/bids.json"))
    parser.add_argument("--mock-dir", type=Path)
    args = parser.parse_args()

    config = load_json(args.config)
    if args.mock_dir:
        source = "mock"
        notices = deduplicate(collect_mock(args.mock_dir, config))
    else:
        service_key = os.environ.get("G2B_SERVICE_KEY", "").strip()
        if not service_key:
            print("G2B_SERVICE_KEY is required for live collection", file=sys.stderr)
            return 2
        source = "KONEPS OpenAPI"
        notices = deduplicate(collect_live(config, service_key))

    notices, filter_counts = apply_filters(notices, config)

    document = {
        "meta": {
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "count": len(notices),
            "schemaVersion": 1,
            "filterCounts": filter_counts,
        },
        "notices": notices,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(notices)} notices to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
