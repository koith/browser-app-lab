#!/usr/bin/env python3
"""Offline safety regression: gallery-dl adapter saves verified individual files."""
import hashlib
import json
import os
import tempfile
from pathlib import Path
from gallery_dl_collector import run

def main():
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp)
        fake=root/"fake-gallery-dl"
        fake.write_text(
            "#!/usr/bin/env python3\n"
            "import pathlib,sys\nfrom PIL import Image\n"
            "args=sys.argv[1:]\n"
            "assert '--zip' not in args and '--cbz' not in args\n"
            "assert '--no-input' in args and '--download-archive' in args\n"
            "target=pathlib.Path(args[args.index('--directory')+1])\n"
            "target.mkdir(parents=True,exist_ok=True)\n"
            "Image.new('RGB',(640,960),(44,55,66)).save(target/'0001.jpg')\n"
        )
        fake.chmod(0o755)
        config=root/"targets.json"
        config.write_text(json.dumps({"sources":[{"id":"safe-source",
            "url":"https://example.org/public-gallery"}]}))
        output=root/"result"
        result=run(config,output,1,2,str(fake))
        assert result["physical_files"]==1
        images=json.loads((output/"photos/safe-source/manifest.json").read_text())["images"]
        assert len(images)==1
        photo=output/"photos/safe-source"/images[0]["path"]
        assert photo.is_file() and hashlib.sha256(photo.read_bytes()).hexdigest()==images[0]["sha256"]
        assert not list(root.rglob("*.zip"))
        assert not list(root.rglob("*.cbz"))
        print("FREE_GALLERY_DL_ADAPTER_INDIVIDUAL_IMAGES_PASS")
if __name__=="__main__":
    main()
