"""Two existing public originals for a credential-free local build, not cloud QA."""
import argparse
import json
from pathlib import Path
import subprocess
from cloudflare_assets_snapshot import Snapshot, signature
from deploy_cloudflare_assets import write_deploy_sources


def fixture(directory):
    root = Path(__file__).resolve().parents[2]
    work = Path(directory).resolve()
    snapshot = Snapshot(root, work / 'assets')
    for model in ('mimmi', 'yui'):
        base = root / f'apps/{model}-gallery'
        stored = json.loads((base / 'stored-albums.json').read_text())
        files = {signature(p): p for a in stored['albums'] for p in a['images']}
        aid, photo = next((aid, p) for (aid, number), p in snapshot.expected[model].items() if signature(p) in files)
        snapshot.add(model, {'id': aid}, photo, (base / files[signature(photo)]['url']).read_bytes(), 'existing-exact-public-copy')
    write_deploy_sources(work / 'source', work / 'assets', snapshot.finish(), 'a' * 32,
                        subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip())
    print('LOCAL_ACTUAL_PUBLIC_JPEG_FIXTURE_ONLY', 'mimmi=1', 'yui=1', 'cloud_uploads=0', flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--directory', required=True)
    fixture(p.parse_args().directory)
