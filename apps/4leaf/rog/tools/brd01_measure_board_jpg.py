#!/usr/bin/env python3
"""BRD-01/M04: measure the original board projection from board.jpg/battle.jpg.

Reproduces docs/evidence/brd01/board-jpg-hex-anchors.json:
  * every visible DMP 0172 tile is located by template matching its native
    145x97 TIS sprite (alpha>200 mask, rows reversed because the PNG export is
    stored bottom-up) at 1:1 scale, TM_CCOEFF_NORMED;
  * 'global' = best match over the whole capture, 'local' = best match within
    +-60 px of the odd-q 105x80(+40) prediction;
  * route structure: how many diagonal DMP route steps of all 26 maps agree
    with an odd-q (odd columns lower) versus even-q hex grid.
Needs: python3, numpy, opencv-python(-headless). Usage:
  python3 tools/brd01_measure_board_jpg.py [maps.json]
maps.json is optional; without it the route check reads original/maps.js.
"""
import json, sys
from pathlib import Path
import cv2
import numpy as np

ROG = Path(__file__).resolve().parents[1]
ASSETS = ROG.parent / 'assets'
TILES = ROG / 'original' / 'Tiles'
CELLS = {14: ('0010', (0, 3)), 15: ('0015', (0, 4)), 16: ('0001', (0, 5)),
         17: ('0017', (0, 6)), 18: ('0028', (1, 6)), 19: ('0006', (2, 7)),
         20: ('0025', (3, 7)), 21: ('0020', (4, 8)), 22: ('0010', (5, 8))}
HEX = dict(pitchX=105, pitchY=80, oddColumnDrop=40)
# cell 17 anchors each capture; the camera of battle.jpg is 35 px lower
ANCHOR17 = {'board': (218.5, 227.5), 'battle': (218.5, 262.5)}


def sprite(art):
    t = cv2.imread(str(TILES / f'{art}.png'), cv2.IMREAD_UNCHANGED)[::-1]
    rgb = t[:, :, :3].astype(np.float32)
    mask = np.dstack([(t[:, :, 3] > 200).astype(np.float32)] * 3)
    return rgb, mask


def predict(capture, dmp):
    ax, ay = ANCHOR17[capture]
    x, y = dmp
    return (ax + (x - 0) * HEX['pitchX'],
            ay + (y - 6) * HEX['pitchY'] + (HEX['oddColumnDrop'] if x & 1 else 0))


def measure():
    out = []
    for capture in ('board', 'battle'):
        img = cv2.imread(str(ASSETS / f'{capture}.jpg')).astype(np.float32)
        pad = np.zeros((img.shape[0] + 400, img.shape[1] + 400, 3), np.float32)
        pad[200:-200, 200:-200] = img
        for cell, (art, dmp) in CELLS.items():
            rgb, mask = sprite(art)
            score = np.nan_to_num(cv2.matchTemplate(pad, rgb, cv2.TM_CCOEFF_NORMED, mask=mask),
                                  nan=-1, posinf=-1, neginf=-1)
            _, g, _, gl = cv2.minMaxLoc(score)
            gx, gy = gl[0] - 200 + 72.5, gl[1] - 200 + 48.5
            px, py = predict(capture, dmp)
            x0, y0 = int(px - 72.5 + 200 - 60), int(py - 48.5 + 200 - 60)
            win = score[max(0, y0):y0 + 121, max(0, x0):x0 + 121]
            _, lv, _, ll = cv2.minMaxLoc(win)
            lx, ly = max(0, x0) + ll[0] - 200 + 72.5, max(0, y0) + ll[1] - 200 + 48.5
            out.append(dict(capture=capture + '.jpg', cell=cell, dmp=dmp, art=art,
                            predicted=[px, py], local=[lx, ly], localScore=round(float(lv), 3),
                            globalBest=[gx, gy], globalScore=round(float(g), 3)))
    return out


def route_structure(maps):
    ok = bad = 0
    exceptions = []
    for key, cells in maps.items():
        for i, (a, b) in enumerate(zip(cells, cells[1:])):
            dx, dy = b[0] - a[0], b[1] - a[1]
            if abs(dx) == 1 and abs(dy) == 1:
                odd = a[0] % 2 == 1
                if (dy == 1 and odd) or (dy == -1 and not odd):
                    ok += 1
                else:
                    bad += 1
                    exceptions.append([key, i, a[:2], b[:2]])
    return dict(oddQConsistent=ok, inconsistent=bad, exceptions=exceptions)


def load_maps(arg):
    if arg:
        data = json.loads(Path(arg).read_text())
        return data.get('maps', data)
    text = (ROG / 'original' / 'maps.js').read_text(encoding='utf8')
    start = text.index('ORIGINAL_LEAF_MAPS=') + len('ORIGINAL_LEAF_MAPS=')
    return json.JSONDecoder().raw_decode(text, start)[0]


def verify_masked():
    """Independent source-only luma correlation through visible duel fragments."""
    evidence = json.loads((ROG / 'docs/evidence/brd01/board-jpg-hex-anchors.json').read_text())
    yy, xx = np.mgrid[:97, :145]
    masks = {
        'right-purple': (xx >= 100) & (yy >= 12) & (yy <= 57),
        'top-clover': (yy <= 30) & (xx >= 40) & (xx <= 105),
        'right-bottom-keeper': ((xx >= 109) & (yy <= 44)) | ((xx >= 42) & (xx <= 103) & (yy >= 79)),
        'battle-right-purple': (xx >= 100) & (yy <= 52),
        'left-bottom-clover': ((xx <= 35) & (yy >= 30) & (yy <= 70)) | ((xx >= 30) & (xx <= 90) & (yy >= 75)),
    }
    rows = []
    for anchor in evidence['anchors']:
        if 'mask' not in anchor:
            continue
        capture = anchor['capture']
        img = cv2.imread(str(ASSETS / capture), cv2.IMREAD_GRAYSCALE).astype(np.float32)
        tile = cv2.imread(str(TILES / (anchor['art'] + '.png')), cv2.IMREAD_UNCHANGED)[::-1]
        lum = (tile[:, :, 0] * .114 + tile[:, :, 1] * .587 + tile[:, :, 2] * .299).astype(np.float32)
        mask = (masks[anchor['mask']] & (tile[:, :, 3] > 200) & (xx % 2 == 0) & (yy % 2 == 0)).astype(np.uint8)
        assert int(mask.sum()) == anchor['sampleCount']
        # Use the prior cell 17 observation plus source DMP coordinate
        # to define the search region, not the newly measured center.
        px, py = predict(capture.removesuffix('.jpg'), anchor['dmp'])
        left, top = int(px - 72.5), int(py - 48.5)
        x0, y0 = max(0, left - 45), max(0, top - 45)
        x1, y1 = min(img.shape[1], left + 45 + 145), min(img.shape[0], top + 45 + 97)
        scores = np.nan_to_num(cv2.matchTemplate(img[y0:y1, x0:x1], lum, cv2.TM_CCOEFF_NORMED, mask=mask),
                               nan=-1, posinf=-1, neginf=-1)
        _, peak, _, (x, y) = cv2.minMaxLoc(scores)
        center = [x0 + x + 72.5, y0 + y + 48.5]
        gy, gx = np.mgrid[:scores.shape[0], :scores.shape[1]]
        alternative = float(scores[(gx - x)**2 + (gy - y)**2 > 16].max())
        assert center == anchor['center'], (anchor, center, peak)
        assert peak > .5 and peak - alternative > .1, (anchor, peak, alternative)
        assert abs(peak - anchor['score']) < .035, (anchor, peak)
        rows.append(dict(capture=capture, cell=anchor['cell'], center=center,
                         score=round(peak, 4), alternative=round(alternative, 4), pixels=int(mask.sum())))
    assert len(rows) == 5 and len(evidence['anchors']) >= 10
    print('BRD-01 ORIGINAL MASKED ANCHORS PASS ' + json.dumps(rows))


def verify_archive():
    """Measure distinct 0172 DMP cells from the original last-night match capture."""
    import hashlib
    from urllib.request import Request, urlopen
    url = 'https://t1.daumcdn.net/cfile/tistory/130D143A5142AFA11F'
    request = Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://4leafmemorial.geld.kr/'})
    with urlopen(request, timeout=25) as response:
        data = response.read()
    frame = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_GRAYSCALE)
    assert frame is not None and frame.shape == (600,800), 'archive must contain the actual 800x600 image'
    yy, xx = np.mgrid[:97, :145]
    # Approximate image windows chosen from the screenshot's actual visible
    # gray tile silhouettes, not the DMP positions. Exclude overlay dice,
    # podium, items, neighboring platform, and fixed right HUD.
    cases = [
        (10, '0015', (166.5,237.5), (xx >= 67) & (xx <= 115) & (yy >= 16) & (yy <= 66)),
        (6, '0015', (586.5,317.5), (xx >= 61) & (xx <= 104) & (yy >= 12) & (yy <= 53)),
        (5, '0015', (691.5,357.5), (xx >= 15) & (xx <= 76) & (yy >= 17) & (yy <= 66)),
        (9, '0007', (271.5,197.5), (xx >= 20) & (xx <= 89) & (yy >= 30) & (yy <= 62)),
    ]
    route = load_maps(None)['0172']
    rows = []
    for cell, art, approx, region in cases:
        rgb = cv2.imread(str(TILES / (art + '.png')), cv2.IMREAD_UNCHANGED)[::-1]
        lum = cv2.cvtColor(rgb, cv2.COLOR_BGRA2GRAY).astype(np.float32)
        mask = (region & (rgb[:,:,3] > 200) & (xx%2==0) & (yy%2==0)).astype(np.uint8)
        left, top = int(approx[0]-72.5), int(approx[1]-48.5)
        x0, y0 = max(0,left-18), max(0,top-18)
        x1, y1 = min(800,left+145+18), min(600,top+97+18)
        scores = np.nan_to_num(cv2.matchTemplate(frame[y0:y1,x0:x1].astype(np.float32),lum,cv2.TM_CCOEFF_NORMED,mask=mask),nan=-1,posinf=-1,neginf=-1)
        _, peak, _, (x,y) = cv2.minMaxLoc(scores)
        gy,gx = np.mgrid[:scores.shape[0],:scores.shape[1]]
        alt = float(scores[(gx-x)**2+(gy-y)**2>16].max())
        row = dict(cell=cell,art=art,dmp=route[cell][:2],center=[x0+x+72.5,y0+y+48.5],score=round(peak,4),alternative=round(alt,4),pixels=int(mask.sum()))
        print('BRD01 ARCHIVE CANDIDATE',json.dumps(row),flush=True)
        if peak >= .58 and peak-alt >= .09:
            rows.append(row)
    # Consensus on the SAME independently measured DMP translation.
    def offset(row):
        x,y=row['dmp']; cx,cy=row['center']
        return (cx-105*x,cy-80*y-40*(x%2))
    consensus=max(([r for r in rows if max(abs(a-b) for a,b in zip(offset(anchor),offset(r))) <= 1] for anchor in rows),key=len,default=[])
    assert len(consensus)>=2, ('need two distinct additional DMP cells with same source translation',rows)
    payload=dict(capture='memorial-130D143A5142AFA11F',url=url,sha256=hashlib.sha256(data).hexdigest(),width=800,height=600,anchors=consensus)
    Path('/tmp/brd01-archive.json').write_text(json.dumps(payload,indent=2)+'\n')
    print('BRD01 ARCHIVE DISTINCT CELLS PASS',json.dumps(payload),flush=True)

if __name__ == '__main__':
    if '--verify-archive' in sys.argv:
        verify_archive()
        sys.exit(0)
    if '--verify-masked' in sys.argv:
        verify_masked()
        sys.exit(0)
    result = dict(projection=HEX, anchors=measure(),
                  routes=route_structure(load_maps(sys.argv[1] if len(sys.argv) > 1 else None)))
    print(json.dumps(result, ensure_ascii=False, indent=1))
