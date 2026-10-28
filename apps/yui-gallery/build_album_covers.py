"""Choose face-visible covers from existing verified files without changing pixels.

Optional local dependency: opencv-python-headless. Facial region detection only;
no identity recognition, embeddings, external service or browser model downloads.
"""
import argparse
import hashlib
import json
from pathlib import Path


def framing(width, height, face):
    x, y, w, h = face
    scale = max(300 / width, 200 / height)
    positions = []
    for total, center, frame, target in [(width, x+w/2, 300, .5),
                                          (height, y+h/2, 200, .47)]:
        overflow = total*scale-frame
        offset = max(0, min(overflow, center*scale-frame*target))
        positions.append(round(100*offset/overflow, 3) if overflow > .001 else 50)
    offsets = [(width*scale-300)*positions[0]/100,
               (height*scale-200)*positions[1]/100]
    # Allow room around the detected face, including hair above its box.
    fits = (x*scale-offsets[0] >= w*scale*.12 and
            (x+w)*scale-offsets[0] <= 300-w*scale*.12 and
            y*scale-offsets[1] >= h*scale*.25 and
            (y+h)*scale-offsets[1] <= 200-h*scale*.1)
    return positions, fits


def build(root, private_root, only_ids=None):
    import cv2
    import numpy as np
    from PIL import Image
    from identity_policy import is_excluded

    classifier = cv2.CascadeClassifier(cv2.data.haarcascades+'haarcascade_frontalface_default.xml')
    eyes = cv2.CascadeClassifier(cv2.data.haarcascades+'haarcascade_eye_tree_eyeglasses.xml')
    paths = {}
    for manifest in private_root.rglob('manifest.json'):
        try:
            data = json.loads(manifest.read_text())
        except (ValueError, OSError):
            continue
        for photo in data.get('images', []):
            filename = photo.get('file', photo.get('path', ''))
            file = (manifest.parent/filename).resolve()
            if filename and file.is_relative_to(private_root.resolve()) and file.is_file():
                paths.setdefault(photo.get('sha256'), file)
    albums = {}
    for name in ['source-viewer-albums.json', 'additional-source-albums.json']:
        albums.update({a['id']: a for a in json.loads((root/name).read_text())['albums']})
    aliases = json.loads((root/'album-aliases.json').read_text())['aliases']
    for a in json.loads((root/'stored-albums.json').read_text())['albums']:
        for p in a['images']:
            paths[p['sha256']] = root/p['url']
        if aliases.get(a['id']) not in albums:
            albums.setdefault(a['id'], a)
    covers, missing = {}, []
    current_path = root/'album-covers.json'
    current = json.loads(current_path.read_text()).get('covers', {}) if current_path.exists() else {}
    for aid, album in albums.items():
        if only_ids and aid not in only_ids:
            if aid in current:
                covers[aid] = current[aid]
            continue
        if is_excluded(aid, album.get('source_pages', []), album['images']):
            continue
        reviewed = current.get(aid)
        if reviewed and reviewed.get('method') == 'manual_face_region_review':
            photo = next((p for p in album['images'] if p['sha256'] == reviewed['sha256']), None)
            file = paths.get(reviewed['sha256'])
            if photo and file and hashlib.sha256(file.read_bytes()).hexdigest() == reviewed['sha256']:
                covers[aid] = reviewed
                print('COVER_MANUAL_REVIEW_PRESERVED', aid, flush=True)
                continue
        fallback = None
        for photo in album['images'][:40]:
            file = paths.get(photo.get('sha256'))
            if not file or not file.is_file():
                continue
            raw = file.read_bytes()
            if hashlib.sha256(raw).hexdigest() != photo['sha256']:
                raise ValueError('Cover source SHA-256 mismatch: '+str(file))
            with Image.open(file) as im:
                width, height = im.size
                ratio = min(1, 1400/max(width, height))
                rgb = np.array(im.convert('RGB').resize((round(width*ratio), round(height*ratio))))
            gray = cv2.equalizeHist(cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY))
            boxes, _, weights = classifier.detectMultiScale3(gray, scaleFactor=1.1, minNeighbors=5,
                                                            minSize=(32, 32), outputRejectLevels=True)
            candidates = []
            for (x, y, w, h), weight in zip(boxes, weights):
                eye_boxes = eyes.detectMultiScale(gray[y:y+int(h*.65), x:x+w], minNeighbors=3)
                if float(weight) < 3.5 or not len(eye_boxes):
                    continue
                face = [round(int(v)/ratio) for v in (x, y, w, h)]
                position, fits = framing(width, height, face)
                candidates.append((fits, int(w*h), float(weight), face, position))
            if not candidates:
                continue
            fits, _, confidence, face, position = max(candidates)
            cover = {'sha256': photo['sha256'], 'number': photo.get('number', 1),
                     'width': width, 'height': height, 'face': face,
                     'position': position, 'fit': 'cover' if fits else 'contain',
                     'method': 'local_face_region_and_eye_detection',
                     'confidence': round(confidence, 3)}
            if fits:
                covers[aid] = cover
                break
            if fallback is None:
                fallback = cover
        if aid not in covers and fallback:
            covers[aid] = fallback
        if aid not in covers:
            missing.append(aid)
        print('COVER_FACE_FRAME', aid, covers.get(aid, {}).get('number'),
              covers.get(aid, {}).get('fit', 'upper_fallback'), flush=True)
    return {'schema_version': 1, 'not_identity_recognition': True,
            'source_pixels_unchanged': True, 'card_aspect_ratio': [3, 2],
            'covers': covers, 'no_confirmed_face_use_upper_fallback': missing}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).parent)
    parser.add_argument('--private-root', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--only', action='append', help='Update only these album IDs; preserve existing covers')
    args = parser.parse_args()
    result = build(args.root, args.private_root, set(args.only or []))
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print('VERIFIED_FACE_COVERS', len(result['covers']),
          'FALLBACKS', len(result['no_confirmed_face_use_upper_fallback']), flush=True)
