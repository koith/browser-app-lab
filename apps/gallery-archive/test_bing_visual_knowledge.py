"""Mocked regression for true Bing image-knowledge JSON, no external calls."""
import json
import unittest
from bing_visual_knowledge import bing_visual_query,pages_including,BING_ENDPOINT

PHOTO="https://koith.github.io/browser-app-lab/apps/mimmi-gallery/images/cover.jpg"
PAGE="https://gallery.example.org/djawa-mimmi-pop-kitty-party"

class Response:
    def __init__(self,body=None,status=200,content_type="application/json"):
        self.status_code=status
        self.headers={"Content-Type":content_type}
        self._body=body
        self.content=json.dumps(body or {}).encode()
    def json(self):
        return self._body

def payload():
    photo={"hostPageUrl":PAGE+"?utm_source=bing",
           "contentUrl":"https://cdn.gallery.example.org/mimmi-original.jpg",
           "name":"Mimmi DJAWA Pop Kitty Party","width":2600,"height":3900}
    return {"_type":"ImageKnowledge","tags":[{"actions":[
        {"actionType":"SimilarImages",
         "data":{"value":[{"hostPageUrl":"https://unrelated.example.org/not-same.jpg"}]}},
        {"actionType":"PagesIncluding","data":{"value":[photo,
         {**photo,"hostPageUrl":PAGE},
         {"hostPageUrl":"http://insecure.example.com/mimmi","name":"Mimmi"},
         {"hostPageUrl":"https://127.0.0.1/internal","name":"Mimmi"}]}}
    ]}]}

class Client:
    def __init__(self,response):
        self.response=response
        self.calls=[]
    def post(self,url,**kwargs):
        self.calls.append((url,kwargs))
        return self.response

class BingVisualTests(unittest.TestCase):
    def test_only_pages_including_provides_same_photo_sources(self):
        rows,seen=pages_including(payload())
        self.assertTrue(seen)
        self.assertEqual(len(rows),1,rows)
        self.assertEqual(rows[0]["url"],PAGE)
        self.assertEqual(rows[0]["matched_width"],2600)
        self.assertEqual(rows[0]["matched_height"],3900)
        self.assertEqual(rows[0]["source_engine"],"bing_visual_pages_including")
        self.assertEqual(rows[0]["matched_image_url"],
                         "https://cdn.gallery.example.org/mimmi-original.jpg")

    def test_bounded_real_visual_search_api_not_bing_html_page(self):
        client=Client(Response(payload()))
        result=bing_visual_query(client,PHOTO)
        self.assertEqual(result["status"],"visual_pages_1",result)
        self.assertEqual(len(result["links"]),1)
        self.assertEqual(len(client.calls),1)
        url,options=client.calls[0]
        self.assertEqual(url,BING_ENDPOINT)
        self.assertEqual(options["allow_redirects"],False)
        self.assertEqual(options["timeout"],(9,26))
        self.assertNotIn("imageBin",str(options))
        request=json.loads(options["files"]["knowledgeRequest"][1])
        self.assertEqual(request["imageInfo"]["url"],PHOTO)

    def test_genuine_empty_visual_response_is_not_generic_html_leads(self):
        client=Client(Response({"tags":[{"actions":[
            {"actionType":"PagesIncluding","data":{"value":[]}}]}]}))
        answer=bing_visual_query(client,PHOTO)
        self.assertEqual(answer,{"status":"visual_pages_0","links":[]})

    def test_http_access_denial_is_not_bypassed_or_counted_as_result(self):
        for code in (302,403,404,429,451):
            with self.subTest(code=code):
                client=Client(Response({},status=code))
                answer=bing_visual_query(client,PHOTO)
                self.assertEqual(answer["links"],[])
                self.assertEqual(answer["status"],
                    "redirect_not_followed" if code==302 else "http_"+str(code))
                self.assertEqual(len(client.calls),1)
        self.assertEqual(bing_visual_query(object(),PHOTO)["status"],
                         "post_not_supported")

    def test_unstructured_response_never_masquerades_as_reverse_matches(self):
        client=Client(Response({"tags":[{"actions":[
            {"actionType":"SimilarImages","data":{"value":[
                {"hostPageUrl":PAGE,"name":"Mimmi"}]}}]}]}))
        result=bing_visual_query(client,PHOTO)
        self.assertEqual(result["status"],"no_pages_including_module")
        self.assertEqual(result["links"],[])

if __name__=="__main__":
    unittest.main()
