import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock
from collector.collect import extract_response, request_page, main, apply_filters, normalize_item
from scripts.validate_data import validate_document

class ReliabilityTests(unittest.TestCase):
    def test_rejects_malformed_api(self):
        for p in ({}, {'unexpected': 1}, {'response': {'header': {'resultCode': '00'}}}):
            with self.assertRaises(ValueError): extract_response(p)

    def test_retry_network_then_success(self):
        payload={'response':{'header':{'resultCode':'00'},'body':{'items':[], 'totalCount':0}}}
        response=MagicMock();response.__enter__.return_value.read.return_value=json.dumps(payload).encode()
        with patch('urllib.request.urlopen',side_effect=[TimeoutError(),response]) as call, patch('time.sleep'):
            request_page('https://example.com','test','dummy',1,100,datetime.now(),datetime.now(),1)
            self.assertEqual(call.call_count,2)

    def test_retry_limit(self):
        with patch('urllib.request.urlopen',side_effect=TimeoutError()) as call,patch('time.sleep'):
            with self.assertRaises(RuntimeError):request_page('https://example.com','test','dummy',1,100,datetime.now(),datetime.now(),1)
            self.assertEqual(call.call_count,4)

    def test_failure_preserves_data_and_records_status(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);out=root/'bids.json';out.write_text('{"sentinel":true}')
            cfg=root/'config.json';cfg.write_text('{}');status=root/'status.json'
            with patch.dict(os.environ,{'G2B_SERVICE_KEY':'dummy'}), patch('collector.collect.collect_live',side_effect=TimeoutError()), patch.object(sys,'argv',['collect','--config',str(cfg),'--output',str(out),'--previous',str(out),'--status',str(status)]):
                self.assertEqual(main(),1)
            self.assertEqual(out.read_text(),'{"sentinel":true}')
            self.assertEqual(json.loads(status.read_text())['state'],'error')

    def test_retains_old_notice(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);out=root/'bids.json';cfg=root/'config.json';status=root/'status.json'
            old=normalize_item({'bidNtceNo':'OLD','bidNtceNm':'교육','bidNtceDt':'2020-01-01 00:00:00'},'services')
            newer=normalize_item({'bidNtceNo':'NEW','bidNtceNm':'행사'},'services')
            out.write_text(json.dumps({'meta':{'source':'KONEPS OpenAPI'},'notices':[old]}))
            cfg.write_text(json.dumps({'filters':{'nationwide':{'enabled':True,'include_all_regions':True}}}))
            with patch.dict(os.environ,{'G2B_SERVICE_KEY':'dummy'}),patch('collector.collect.collect_live',return_value=[newer]),patch.object(sys,'argv',['collect','--config',str(cfg),'--output',str(out),'--previous',str(out),'--status',str(status)]):
                self.assertEqual(main(),0)
            self.assertEqual({n['noticeNo'] for n in json.loads(out.read_text())['notices']},{'OLD','NEW'})

    def test_unknown_region_retained_as_unverified(self):
        cfg={'filters':{'nationwide':{'enabled':True,'include_all_regions':True}}}
        n=normalize_item({'bidNtceNo':'A','bidNtceNm':'행사','dminsttNm':'기관'},'services')
        result,_=apply_filters([n],cfg)
        self.assertEqual(result[0]['matches']['groupIds'],['nationwide'])
        self.assertIn('확인 필요',result[0]['eligibility'])

    def test_rejects_broken_notice(self):
        with self.assertRaises(ValueError):validate_document({'meta':{'source':'KONEPS OpenAPI','generatedAt':'2026-10-08T00:00:00+00:00','count':1},'notices':[{'id':'x'}]})
