import unittest
from public_work_photo_extractor import recover_public_work_photo_urls


class ExtractorTests(unittest.TestCase):
    def test_extra_public_images_in_scoped_article(self):
        page='https://www.junmeitu.com/yui-sim/summer/'
        raw='''<title>Yui Sim Summer</title><article>
          <a href="https://images.example.com/full-01.jpg"><img src="/small-01.jpg"></a>
          <picture><source srcset="https://images.example.com/full-02.webp 2x, /small-02.webp 1x"></picture>
          <img data-original="https://images.example.com/original?id=3">
          <div class="related"><img src="https://images.example.com/unrelated.jpg"></div>
        </article>'''
        urls,status=recover_public_work_photo_urls(raw,page,'yui',trusted_work=True)
        self.assertEqual(status,'article_image_attributes')
        self.assertIn('https://images.example.com/full-01.jpg',urls)
        self.assertIn('https://images.example.com/full-02.webp',urls)
        self.assertIn('https://images.example.com/original?id=3',urls)
        self.assertNotIn('https://images.example.com/unrelated.jpg',urls)

    def test_different_model_and_unregistered_page(self):
        page='https://www.junmeitu.com/other/'
        raw='<title>Other Person</title><article><img src="https://images.example.com/1.jpg"></article>'
        self.assertEqual(recover_public_work_photo_urls(raw,page,'yui',trusted_work=True)[0],[])
        self.assertEqual(recover_public_work_photo_urls(raw,page,'yui',trusted_work=False)[0],[])


if __name__=='__main__':
    unittest.main()
