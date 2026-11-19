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


if __name__ == '__main__':
    result = dict(projection=HEX, anchors=measure(),
                  routes=route_structure(load_maps(sys.argv[1] if len(sys.argv) > 1 else None)))
    print(json.dumps(result, ensure_ascii=False, indent=1))
