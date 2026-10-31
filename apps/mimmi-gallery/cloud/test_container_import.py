"""Import exactly the Python files selected by the production Dockerfile."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

root=Path(__file__).parent/'gateway'
dockerfile=(root/'Dockerfile').read_text()
with tempfile.TemporaryDirectory() as directory:
    target=Path(directory)
    for source in re.findall(r'^COPY (.+) \./\s*$',dockerfile,re.M):
        for pattern in source.split():
            for file in root.glob(pattern):
                if file.is_file():shutil.copyfile(file,target/file.name)
    env={**os.environ,'PYTHONPATH':'','GALLERY_ACCESS_TOKEN':'offline-fixture-only',
         'RCLONE_CONFIG_ARCHIVE_COOKIE':'offline-fixture-only'}
    result=subprocess.run([sys.executable,'-c','import main; assert main.app.title'],
        cwd=target,env=env,capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stderr[-1500:]
print('PRODUCTION_DOCKER_COPY_SET_IMPORT_PASS')
