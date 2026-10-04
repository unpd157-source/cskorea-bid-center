import json
import tempfile
import unittest
from pathlib import Path

from collector.collect import apply_filters, deduplicate, extract_response, normalize_item


class CollectorTests(unittest.TestCase):
    def test_extracts_official_response_envelope(self):
        payload = {"response": {"header": {"resultCode": "00"}, "body": {
            "totalCount": 1, "items": [{"bidNtceNo": "1"}]
        }}}
        items, total = extract_response(payload)
        self.assertEqual(total, 1)
        self.assertEqual(items[0]["bidNtceNo"], "1")

    def test_normalizes_and_deduplicates_notice_revision(self):
        raw = {"bidNtceNo": "A", "bidNtceOrd": "01", "bidNtceNm": "행사"}
        notice = normalize_item(raw, "services")
        result = deduplicate([notice, notice])
        self.assertEqual(result[0]["id"], "A-01")
        self.assertEqual(len(result), 1)

    def test_raises_api_error(self):
        with self.assertRaisesRegex(RuntimeError, "KONEPS API error 30"):
            extract_response({"response": {"header": {
                "resultCode": "30", "resultMsg": "SERVICE KEY IS NOT REGISTERED"
            }}})

    def test_filters_local_institution_and_nationwide_region(self):
        config = {
            "filters": {
                "keywords": ["행사"],
                "exclude_keywords": [],
                "institution_groups": [{
                    "id": "ulsan_city", "label": "울산시", "enabled": True,
                    "institution_names": ["울산광역시"]
                }],
                "nationwide": {
                    "enabled": True, "label": "전국",
                    "allowed_regions": ["전국"], "allow_unknown_region": False
                }
            }
        }
        local = normalize_item({
            "bidNtceNo": "1", "bidNtceNm": "축제 행사 운영",
            "dminsttNm": "울산광역시", "prtcptPsblRgnNm": "울산"
        }, "services")
        national = normalize_item({
            "bidNtceNo": "2", "bidNtceNm": "국제 행사 운영",
            "dminsttNm": "한국기관", "prtcptPsblRgnNm": "전국"
        }, "services")
        unknown = normalize_item({
            "bidNtceNo": "3", "bidNtceNm": "지역 행사 운영",
            "dminsttNm": "타지역기관"
        }, "services")
        matched, counts = apply_filters([local, national, unknown], config)
        self.assertEqual([item["id"] for item in matched], ["1-00", "2-00"])
        self.assertEqual(counts, {"ulsan_city": 1, "nationwide": 1})

    def test_excluded_keyword_wins(self):
        config = {"filters": {
            "keywords": ["교육"], "exclude_keywords": ["시설공사"],
            "institution_groups": [{
                "id": "edu", "label": "교육청", "enabled": True,
                "institution_names": ["교육청"]
            }],
            "nationwide": {"enabled": False}
        }}
        item = normalize_item({
            "bidNtceNo": "4", "bidNtceNm": "교육 시설공사",
            "dminsttNm": "울산광역시교육청"
        }, "services")
        matched, _ = apply_filters([item], config)
        self.assertEqual(matched, [])


if __name__ == "__main__":
    unittest.main()
