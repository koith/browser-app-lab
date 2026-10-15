import importlib.util, os, tempfile, unittest
from unittest.mock import patch
from pathlib import Path
spec=importlib.util.spec_from_file_location("watch",str(Path(__file__).with_name("chiikawa_lotte_watch.py")))
watch=importlib.util.module_from_spec(spec);spec.loader.exec_module(watch)
class Tests(unittest.TestCase):
 def test_no_candidate_no_alert(self):
  with patch.object(watch,"fetch",return_value=("https://search.shopping.naver.com","<html>nothing</html>")):
   self.assertIsNone(watch.check())
 def test_live_product_detected(self):
  url="https://m.brand.naver.com/lottecinema/products/123456"
  def fake_fetch(u):
   if "search.shopping" in u:return u,'<a href="'+url+'">link</a>'
   return u,'<html>먼작귀 렌티큘러 예약구매 <script type="application/ld+json">{"availability":"https://schema.org/InStock"}</script></html>'
  with patch.object(watch,"fetch",side_effect=fake_fetch):
   self.assertEqual(watch.check()["url"],url)
 def test_sold_out_suppressed(self):
  url="https://m.brand.naver.com/lottecinema/products/123456"
  def fake_fetch(u):
   if "search.shopping" in u:return u,url
   return u,'먼작귀 렌티큘러 예약구매 품절 https://schema.org/InStock'
  with patch.object(watch,"fetch",side_effect=fake_fetch):
   self.assertIsNone(watch.check())
 def test_escaped_url(self):
  url="https://m.brand.naver.com/lottecinema/products/123456"
  def fake_fetch(u):
   if "search.shopping" in u:return u,url.replace("/","\\/")
   return u,'먼작귀 렌티큘러 예약구매 https://schema.org/InStock'
  with patch.object(watch,"fetch",side_effect=fake_fetch):
   self.assertEqual(watch.check()["url"],url)
if __name__=="__main__":unittest.main()
