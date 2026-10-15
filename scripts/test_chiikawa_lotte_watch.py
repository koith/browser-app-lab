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

    def test_ntfy_push_contains_direct_link_and_urgent_priority(self):
        product={"kind":"lenticular","label":"렌티큘러 스티커","title":"먼작귀 렌티큘러","url":"https://m.brand.naver.com/lottecinema/products/222"}
        response=MagicMock()
        response.status=200
        response.__enter__.return_value=response
        with patch.dict(os.environ,{"NTFY_TOPIC":"test-topic"},clear=False):
            with patch.object(watch.urllib.request,"urlopen",return_value=response) as call:
                watch.send_ntfy(product)
                request=call.call_args[0][0]
                self.assertEqual(request.full_url,"https://ntfy.sh/test-topic")
                self.assertEqual(request.get_method(),"POST")
                self.assertIn("먼작귀",request.data.decode("utf-8"))
                self.assertEqual(request.get_header("Priority"),"5")
                self.assertEqual(request.get_header("Click"),product["url"])

    def test_purchase_button_triggers_second_stage(self):
        item={"kind":"lenticular","label":"렌티큘러 스티커","title":"먼작귀 렌티큘러","url":"https://m.brand.naver.com/lottecinema/products/222"}
        detail="Title: 먼작귀 렌티큘러 : 롯데시네마 스토어\n\n상품 옵션\n\n구매하기\n\n찜 하기 톡톡문의 장바구니"
        self.assertTrue(watch.buy_button_visible(detail,item))
        catalog="롯데시네마 "+card("먼작귀 렌티큘러 띠부띠부 씰",222)
        def fake_fetch(url):
            return url, detail if "/products/222" in url else catalog
        with patch.object(watch,"fetch",side_effect=fake_fetch):
            result=watch.check()
            self.assertEqual(result[0]["stage"],"buy_button")
    def test_disabled_purchase_button_suppressed(self):
        item={"kind":"lenticular","label":"렌티큘러 스티커","title":"먼작귀 렌티큘러","url":"https://m.brand.naver.com/lottecinema/products/222"}
        detail="Title: 먼작귀 렌티큘러 : 롯데시네마 스토어\n\n판매 예정\n\n구매하기\n\n찜 하기"
        self.assertFalse(watch.buy_button_visible(detail,item))
    def test_buy_button_is_not_inferred_from_other_product(self):
        item={"kind":"lenticular","label":"렌티큘러 스티커","title":"먼작귀 렌티큘러","url":"https://m.brand.naver.com/lottecinema/products/222"}
        detail="Title: 포켓몬스터 키링 : 롯데시네마 스토어\n\n구매하기\n\n찜 하기"
        self.assertFalse(watch.buy_button_visible(detail,item))

if __name__=="__main__": unittest.main()
