"""Public-post scope, original-byte preservation, resume and robots regression checks."""
import hashlib
import io
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PIL import Image

from public_photo_archive import PublicSession, download_individuals, verified_record
from sns_archive import discover, record_page


class PublicPhotoTests(unittest.TestCase):
    def test_empty_video_page_does_not_end_photo_pagination(self):
        class Client:
            def get(self, url):
                import requests
                second = 'cursor=second' in url
                third = 'cursor=third' in url
                photo = '' if second else '''<div class="timeline-item" data-username="super_yuisan">
                  <a class="tweet-link" href="/super_yuisan/status/1#m"></a>
                  <div class="attachments"><a class="still-image"
                  href="https://pbs.twimg.com/media/'''+('last' if third else 'first')+'''.jpg?name=orig"></a></div></div>'''
                next_link = '' if third else '<a href="/super_yuisan/media?cursor='+('third' if second else 'second')+'">Load more</a>'
                response = requests.Response();response.status_code=200
                response._content=(photo+next_link).encode();response.encoding='utf-8'
                return response
        result = discover(Client(), max_pages=5, delay=0)
        self.assertEqual(len(result['images']), 2)
        self.assertEqual(len(result['pages']), 3)
        self.assertFalse(result['truncated'])

    def test_posts_exclude_quoted_retweeted_and_unlinked_previews(self):
        original = 'https://pbs.twimg.com/media/own.jpg?name=orig'
        html = '''<div class="timeline-item" data-username="super_yuisan">
          <a class="tweet-link" href="/super_yuisan/status/123#m"></a>
          <div class="tweet-content">#Cosplay credit @photographer</div>
          <div class="attachments"><a class="still-image" href="''' + original + '''"></a></div>
          <div class="quote"><div class="attachments"><a class="still-image"
            href="https://pbs.twimg.com/media/quoted.jpg?name=orig"></a></div></div>
          <img src="https://pbs.twimg.com/media/unlinked.jpg?name=small">
          </div><div class="timeline-item" data-username="unrelated">
          <a class="tweet-link" href="/unrelated/status/456#m"></a>
          <div class="attachments"><a class="still-image"
            href="https://pbs.twimg.com/media/retweet.jpg?name=orig"></a></div></div>
          <a href="/super_yuisan/media?cursor=next">Load more</a>
          <a href="https://bad.example/super_yuisan/media?cursor=other">Next</a>'''
        rows, nexts = record_page(html, 'https://teapawt.net/super_yuisan/media')
        self.assertEqual([r['url'] for r in rows], [original])
        self.assertEqual(rows[0]['post'], 'https://x.com/super_yuisan/status/123')
        self.assertEqual(nexts, ['https://teapawt.net/super_yuisan/media?cursor=next'])

    def test_individual_bytes_resume_dedup_and_tamper_detection(self):
        buffer = io.BytesIO()
        Image.new('RGB', (300, 400), '#443366').save(buffer, format='PNG')
        fixture = buffer.getvalue()
        requests_seen = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                requests_seen.append(self.path)
                if self.path == '/robots.txt':
                    raw = b'User-agent: *\nDisallow: /denied\n'
                else:
                    raw = fixture
                self.send_response(200)
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = 'http://127.0.0.1:' + str(server.server_port)
            records = [{'url': base + '/a'}, {'url': base + '/b'}, {'url': base + '/denied'}]
            client = PublicSession(delay=0, allow_local_test=True)
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                report = download_individuals(records, root, client)
                self.assertEqual(report['unique_files'], 1)
                self.assertEqual(len(report['images']), 2)
                self.assertEqual(len(report['failures']), 1)
                self.assertNotIn('/denied', requests_seen)
                row = report['images'][0]
                self.assertEqual((root / row['file']).read_bytes(), fixture)
                self.assertEqual(row['sha256'], hashlib.sha256(fixture).hexdigest())
                request_count = len(requests_seen)
                again = download_individuals(records[:2], root, client)
                self.assertEqual(again['new_unique_files_this_run'], 0)
                self.assertEqual(again['skipped_existing_urls'], 2)
                self.assertEqual(len(requests_seen), request_count)
                self.assertEqual(len(list(root.rglob('*.png'))), 1)
                self.assertEqual(list(root.rglob('*.zip')), [])
                (root / row['file']).write_bytes(fixture + b'changed')
                with self.assertRaisesRegex(ValueError, 'integrity mismatch'):
                    verified_record(root, row)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    unittest.main()
