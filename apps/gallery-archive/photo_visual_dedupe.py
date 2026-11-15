"""Compare new public JPG bytes against SAME-WORK saved photo pixels before append.

An unmatched SHA is only a new encoding, not a new photographic cut. Reject
confirmed same-frame recompressions but never delete original data, accept
unrelated works, infer copyright/publisher completeness, or replace a source
without a separate verified upgrade transaction.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
from perceptual_duplicate_audit import scan_image, candidate_relation
from photo_quality_evidence import preferred_pair


class WorkVisualIndex:
    def __init__(self, base, album):
        self.base=Path(base).resolve()
        self.album=album
        self.entries=[]
        self.reference_missing=0
        self.reference_corrupt=0
        self._load()

    def _load(self):
        from PIL import Image
        aid=self.album['id']
        seen=set()
        for row in self.album.get('images',[]):
            rel=row.get('url','')
            digest=row.get('sha256')
            if (not isinstance(rel,str) or
                    not rel.startswith('stored-albums/'+aid+'/') or
                    not isinstance(digest,str) or digest in seen):
                continue
            seen.add(digest)
            path=(self.base/rel).resolve()
            if not path.is_relative_to(self.base) or not path.is_file():
                self.reference_missing+=1
                continue
            try:
                raw=path.read_bytes()
                if hashlib.sha256(raw).hexdigest()!=digest:
                    self.reference_corrupt+=1
                    continue
                scanned=scan_image(raw)
                # Keep only tiny fingerprint + pathname; full originals may
                # collectively be gigabytes in a public photobook.
                self.entries.append((dict(row),scanned,path))
            except (OSError,ValueError,Image.DecompressionBombError):
                self.reference_corrupt+=1

    def classify(self, raw):
        """Only a very tight pixel match establishes a duplicate existing cut."""
        try:
            candidate=scan_image(raw)
        except (ValueError,OSError):
            # Oversize originals are still allowed by the existing physical
            # decoder; no new runtime failure should block their publication.
            return None
        for row,old_scan,old_path in self.entries:
            relation,distance,diff=candidate_relation(old_scan,candidate)
            if (relation!='perceptually_similar_review' or
                    distance is None or distance>3 or diff is None or diff>2.0):
                continue
            try:
                old_raw=old_path.read_bytes()
            except OSError:
                continue
            upgrade,evidence=preferred_pair(
                old_raw,raw,row['sha256'],
                row.get('watermark_status','unknown'),'unknown')
            if not evidence.get('same_photo_verified'):
                continue
            return {'existing_number':row.get('number'),
                    'existing_sha256':row['sha256'],
                    'new_sha256':candidate['sha256'],
                    'visual_comparison':'strict_same_cut_reencode',
                    'distance':distance,'pixel_difference':diff,
                    'quality_relation':evidence.get('relation'),
                    'needs_replacement_transaction':bool(upgrade)}
        return None

    def remember(self, row, raw):
        """Prevent two different encodings of a newly staged cut in one batch."""
        try:
            scanned=scan_image(raw)
        except (ValueError,OSError):
            return
        rel=row.get('url','')
        if not isinstance(rel,str):
            return
        path=(self.base/rel).resolve()
        if not path.is_relative_to(self.base):
            return
        self.entries.append((dict(row),scanned,path))
