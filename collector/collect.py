#!/usr/bin/env python3
"""Collect and normalize KONEPS bid notices into a static JSON file.

Strict API validation, bounded retries and cumulative notice retention.
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
    if not isinstance(payload, dict) or not isinstance(payload.get("response"), dict):
        raise ValueError("Missing API response envelope")
    response = payload["response"]
    header = response.get("header")
    if not isinstance(header, dict) or "resultCode" not in header:
        raise ValueError("Missing API result code")
    result_code = str(header["resultCode"])
    if result_code not in {"00", "0"}:
        raise RuntimeError(f"KONEPS API error {result_code}")
    body = response.get("body")
    if not isinstance(body, dict) or "totalCount" not in body or "items" not in body:
        raise ValueError("Missing API result body")
    total = int(body["totalCount"])
    if total < 0:
        raise ValueError("Invalid totalCount")
    items = body["items"]
    if isinstance(items, dict):
        items = items.get("item", [])
    if items in (None, ""):
        items = []
    if isinstance(items, dict):
        items = [items]
    if not isinstance(items, list) or any(not isinstance(i, dict) for i in items):
        raise ValueError("Invalid API items")
    if any(not i.get("bidNtceNo") or not i.get("bidNtceNm") for i in items):
        raise ValueError("Missing required notice fields")
    if total == 0 and items:
        raise ValueError("Inconsistent API totalCount")
    return items, total


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
    # Never log request URLs: they contain the service key.
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            extract_response(payload)
            return payload
        except urllib.error.HTTPError as exc:
            if exc.code not in {408, 429, 500, 502, 503, 504}:
                raise RuntimeError(f"HTTP {exc.code} from {operation}") from None
            reason = f"HTTP {exc.code}"
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            reason = "network timeout or connection failure"
        except (ValueError, RuntimeError):
            reason = "invalid API response or API rejection"
        if attempt == 3:
            raise RuntimeError(f"Collection failed from {operation}: {reason}") from None
        print(f"Retry {attempt + 1}/3 for {operation}", flush=True)
        time.sleep(2 ** (attempt + 1))
    raise RuntimeError("Collection failed")


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
            if not items and received < total_count:
                raise ValueError("API returned an incomplete page sequence")
            received += len(items)
            if received >= total_count:
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
            region_ok = nationwide.get("include_all_regions", False) or (
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
            enriched["eligibility"] = "참가 자격·지역 제한 원문 확인 필요"
            matched.append(enriched)

    return matched, counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("config.json"))
    parser.add_argument("--output", type=Path, default=Path("public/data/bids.json"))
    parser.add_argument("--mock-dir", type=Path)
    parser.add_argument("--previous", type=Path, default=Path("public/data/bids.json"))
    parser.add_argument("--status", type=Path, default=Path("public/data/status.json"))
    args = parser.parse_args()
    attempted = datetime.now(timezone.utc).isoformat()
    try:
        config = load_json(args.config)
        previous = load_json(args.previous) if args.previous.exists() else {}
        if args.mock_dir:
            if args.output.resolve() == Path("public/data/bids.json").resolve():
                raise ValueError("Mock output must use a separate --output path")
            source = "mock"
            raw_notices = deduplicate(collect_mock(args.mock_dir, config))
            old_notices = []
        else:
            service_key = os.environ.get("G2B_SERVICE_KEY", "").strip()
            if not service_key:
                raise ValueError("G2B_SERVICE_KEY is required")
            source = "KONEPS OpenAPI"
            raw_notices = deduplicate(collect_live(config, service_key))
            if not raw_notices:
                raise ValueError("Empty API collection; retaining previous data")
            old_notices = previous.get("notices", []) if previous.get("meta", {}).get("source") == source else []
        # Merge BEFORE filtering, so changed rules also apply to retained notices.
        # New records win over previous copies with the same ID.
        merged = deduplicate([*old_notices, *raw_notices])
        notices, filter_counts = apply_filters(merged, config)
        now = datetime.now(timezone.utc).isoformat()
        document = {"meta": {"generatedAt": now, "source": source,
            "count": len(notices), "schemaVersion": 2, "filterCounts": filter_counts,
            "fetchedCount": len(raw_notices), "retention": "cumulative",
            "coverage": "Keyword-matched services; institution-name rules; eligibility unverified"},
            "notices": notices}
        if not args.mock_dir:
            from scripts.validate_data import validate_document
            validate_document(document)
        atomic_json(args.output, document)
        if not args.mock_dir:
            atomic_json(args.status, {"state": "success", "attemptedAt": attempted,
                "lastSuccessAt": now, "message": "공고 수집 완료", "count": len(notices)})
        print(f"Wrote {len(notices)} notices to {args.output}", flush=True)
        return 0
    except Exception as exc:
        if not args.mock_dir:
            # Exception text or traceback can contain a service key; publish only a safe code.
            atomic_json(args.status, {"state": "error", "attemptedAt": attempted,
                "message": "나라장터 수집 실패. 마지막 성공 자료를 유지합니다.",
                "errorType": type(exc).__name__})
        print(f"Collection failed ({type(exc).__name__}); previous data retained", file=sys.stderr)
        return 1


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


if __name__ == "__main__":
    raise SystemExit(main())
