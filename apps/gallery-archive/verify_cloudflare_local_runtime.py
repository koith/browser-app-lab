"""Real local workerd acceptance; no cloud credentials or resource operations."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from urllib.error import HTTPError
from urllib.request import urlopen
from cloudflare_assets_local_fixture import fixture
from cloudflare_assets_snapshot import checked
from deploy_cloudflare_assets import media_bytes, MODELS


def run(directory):
    work = Path(directory).resolve()
    fixture(work)
    (work / 'source/.dev.vars').write_text('SIGNING_KEY=local-fixture-only-key-01234567890123456789012345\n')
    base = 'http://127.0.0.1:8791'
    log = (work / 'local-runtime.log').open('wb')
    process = subprocess.Popen(['npx', '--yes', 'wrangler@4.158.0', 'dev', '--local', '--ip', '127.0.0.1',
        '--port', '8791', '--show-interactive-dev-session=false', '--config', str(work / 'source/wrangler.json')],
        env={**os.environ, 'WRANGLER_SEND_METRICS': 'false'}, stdout=log, stderr=subprocess.STDOUT,
        start_new_session=True, cwd=work / 'source')
    try:
        ready = False
        for _ in range(45):
            if process.poll() is not None:
                raise AssertionError('Actual workerd failed to start')
            try:
                with urlopen(base + '/api/v1/health', timeout=2) as response:
                    ready = json.load(response).get('transport') == 'cloudflare-bound-assets'
                if ready:
                    break
            except OSError:
                pass
            time.sleep(1)
        assert ready, 'Actual workerd not ready within45s'
        for model in MODELS:
            data = json.loads((work / f'source/private-{model}-catalog.txt').read_text())
            album = data['albums'][0]; photo = album['images'][0]
            raw = media_bytes(base, model, album['id'], photo)
            checked(photo, raw)
            for path in (model + '/metadata/catalog.json', model + '/' + photo['key']):
                try:
                    urlopen(base + '/' + path, timeout=10)
                except HTTPError as error:
                    assert error.code == 404
                    continue
                raise AssertionError('Raw private namespace was exposed')
            print('ACTUAL_LOCAL_WORKERD_SHA_BYTES_PIXELS_AND_RAW_DENIAL_PASS', model,
                  photo['width'], photo['height'], 'cloud_uploads=0', flush=True)
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=15)
        log.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--directory', required=True)
    run(parser.parse_args().directory)
