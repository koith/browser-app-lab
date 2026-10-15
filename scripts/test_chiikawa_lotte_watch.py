import importlib.util
import os
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

spec=importlib.util.spec_from_file_location("watch",str(Path(__file__).with_name("chiikawa_lotte_watch.py")))
watch=importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch)

def card(title,number):
    return "[상품 상세보기](https://m.brand.naver.com/lottecinema/products/"+str(number)+")**"+title+"** 3,900 원"

class WatchTests(unittest.TestCase):
    def test_no_target_no_alert(self):
        body="롯데시네마 "+card("[롯데시네마] 먼작귀 먹방 피규어",111)
        with patch.object(watch,"fetch",return_value=("https://r.jina.ai/",body)):
            self.assertEqual(watch.check(),[])
    def test_lenticular_detected(self):
        body="롯데시네마 "+card("[롯데시네마] 먼작귀 렌티큘러 띠부띠부 씰",222)
        with patch.object(watch,"fetch",return_value=("https://r.jina.ai/",body)):
            self.assertEqual(watch.check()[0]["kind"],"lenticular")
    def test_charm_detected(self):
        body="롯데시네마 "+card("[롯데시네마] 먼작귀 USB-C 케이블 커버 참",333)
        with patch.object(watch,"fetch",return_value=("https://r.jina.ai/",body)):
            self.assertEqual(watch.check()[0]["kind"],"usb-charm")
    def test_both_alerts_not_just_first(self):
        body="롯데시네마 "+card("먼작귀 렌티큘러 띠부띠부 씰",222)+card("먼작귀 C타입 케이블 커버 참",333)
        with patch.object(watch,"fetch",return_value=("https://r.jina.ai/",body)):
            self.assertEqual({p["kind"] for p in watch.check()},{"lenticular","usb-charm"})
    def test_escaped_and_wrong_product_ignored(self):
        body="롯데시네마 "+card("먼작귀 먹방 피규어",111)+card("포켓몬 렌티큘러",444)
        with patch.object(watch,"fetch",return_value=("https://r.jina.ai/",body)):
            self.assertEqual(watch.check(),[])
    def test_no_network_no_false_success(self):
        with patch.object(watch,"fetch",side_effect=RuntimeError("HTTP 429")):
            with self.assertRaises(RuntimeError):
                watch.check()
    def test_only_one_source_needed(self):
        body="롯데시네마 "+card("먼작귀 렌티큘러 씰",222)
        calls=[RuntimeError("blocked"),("https://r.jina.ai/",body)]
        with patch.object(watch,"fetch",side_effect=calls):
            self.assertEqual(watch.check()[0]["kind"],"lenticular")
    def test_deduplicate_notifications(self):
        body="롯데시네마 "+card("먼작귀 렌티큘러 씰",222)
        fake=MagicMock()
        fake.stdout="[먼작귀 예약상품 등록 감지] 렌티큘러 스티커\n"
        with patch.dict(os.environ,{"GH_TOKEN":"test","GITHUB_REPOSITORY":"koith/browser-app-lab"}):
            with patch.object(watch.subprocess,"run",return_value=fake) as cmd:
                watch.send_issue_alerts(watch.parse_catalog(body))
                self.assertEqual(cmd.call_count,1)
    def test_creates_alert_with_mention_and_assignee(self):
        body="롯데시네마 "+card("먼작귀 렌티큘러 씰",222)
        fake=MagicMock()
        fake.stdout=""
        with patch.dict(os.environ,{"GH_TOKEN":"test","GITHUB_REPOSITORY":"koith/browser-app-lab"}):
            with patch.object(watch.subprocess,"run",return_value=fake) as cmd:
                watch.send_issue_alerts(watch.parse_catalog(body))
                self.assertEqual(cmd.call_count,2)
                args=cmd.call_args[0][0]
                self.assertIn("--assignee",args)
                self.assertIn("@koith"," ".join(args))
                self.assertIn("https://m.brand.naver.com/lottecinema/products/222"," ".join(args))

if __name__=="__main__": unittest.main()
