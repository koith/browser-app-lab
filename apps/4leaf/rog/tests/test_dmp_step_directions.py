#!/usr/bin/env python3
"""26 original DMP route vectors, with 8-direction movement verified.

The mapping from these directions to OBS frame blocks is NOT decoded.
"""
import collections,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
UNIT=[(0,1),(0,-1),(1,0),(-1,0),(1,1),(1,-1),(-1,1),(-1,-1)]
def main():
    routes=json.loads((ROOT/"original/maps.json").read_text(encoding="utf-8"))["routes"]
    assert len(routes)==26,len(routes)
    steps=collections.Counter();parity=collections.Counter()
    for row in routes.values():
        for a,b in zip(row,row[1:]):
            d=(b[0]-a[0],b[1]-a[1]);steps[d]+=1
            if d in UNIT and d[0] and d[1]:
                parity[a[1]%2]+=1
    total=sum(steps.values());unit=sum(steps[d] for d in UNIT)
    assert total==1894,(total,unit)
    assert unit==1828,(total,unit)
    assert all(steps[d]>0 for d in UNIT),steps
    assert parity[0] and parity[1],parity
    out={"source":"original/maps.json (26 DMP routes)","steps":total,"unitSteps":unit,
         "unitShare":round(unit/total,4),"vectors":{"%d,%d"%d:steps[d] for d in UNIT},
         "longerJumps":{"%d,%d"%d:n for d,n in steps.most_common() if d not in UNIT},
         "diagonalStepsByRowParity":{"even":parity[0],"odd":parity[1]},
         "spriteFacingBlocks":{"rear":"0-10","sideLeft":"11-21","front":"22-32","lunge":"33-36"},
         "exeDirectionRule":"UNDECODED"}
    expected=json.loads((ROOT/"docs/evidence/dmp-step-directions.json").read_text())
    assert out==expected,(out,expected)
    print("DMP STEP DIRECTIONS PASS",json.dumps({k:out[k] for k in ("steps","unitShare","vectors")}))
if __name__=="__main__":main()
