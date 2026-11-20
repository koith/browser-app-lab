#!/usr/bin/env python3
"""Use the existing gallery collector with an official-publisher-only transport.

No mirrors, login, payment, guessed resources, or redirection outside the
publisher's ordinary public article/preview origin.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlsplit
from direct_photo_pipeline import collect, PublicSession
from official_sample_recovery import _publisher_page, _publisher_photo

ROOT=Path(__file__).resolve().parents[2]
class OfficialPublicSession(PublicSession):
    def _origin(self,url):
        p=urlsplit(url)
        if (p.hostname not in ("djawaphoto.com","www.djawaphoto.com")
            or p.scheme!="https" or p.port not in (None,443)
            or p.username or p.password):
            raise ValueError("outside official publisher origin")
        return super()._origin(url)
    def _raw(self,url):
        self._origin(url)
        if not (_publisher_page(url) or _publisher_photo(url)
                or urlsplit(url).path=="/robots.txt"):
            raise ValueError("not an observed official public sample or article")
        return super()._raw(url)
    def get(self,url):
        if not (_publisher_page(url) or _publisher_photo(url)):
            raise ValueError("not official public article or photo")
        return super().get(url)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--model",choices=("yui","mimmi"),required=True)
    p.add_argument("--evidence",type=Path,required=True)
    p.add_argument("--stage",type=Path,required=True)
    a=p.parse_args()
    owner=json.loads((ROOT/"apps"/(a.model+"-gallery")/"owner-index.json").read_text())
    evidence=json.loads(a.evidence.read_text())
    if evidence.get("model")!=a.model or evidence.get("schema_version")!=1:
        raise ValueError("wrong evidence model")
    ids=list(dict.fromkeys(r["id"] for r in evidence.get("targets",[])
             if re.fullmatch(r"[a-z0-9][a-z0-9-]{1,100}",str(r.get("id","")))
             and any(_publisher_page(u) for u in r.get("urls",[]))))
    if not ids:print("OFFICIAL_NO_VALID_TARGETS",a.model);return
    # Known, missing official samples and lower held counts are prioritized
    # by the existing collector; rotate later batches instead of dropping.
    for offset in range(0,len(ids),12):
        stage=a.stage/("batch-"+str(offset//12))
        report=collect(ROOT,a.model,owner,stage,max_new=60,max_pages=6,
                       client=OfficialPublicSession(delay=0.85),
                       album_ids=ids[offset:offset+12],render_budget=0,
                       reverse_evidence=a.evidence,reviewed_source_only=True)
        print("OFFICIAL_REAL_STAGE",a.model,len(report["results"]),report["new_local_individual_files"],flush=True)
        for row in report["results"]:
            print("OFFICIAL_WORK_RESULT",row["id"],row.get("individual_files_saved",0),
                  row.get("published_image_candidates",0),len(row.get("failures",[])),flush=True)
if __name__=="__main__":main()
