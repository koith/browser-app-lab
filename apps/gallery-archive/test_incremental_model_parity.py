#!/usr/bin/env python3
"""Offline: incremental replacement preserves saved originals for both models.

All files/catal ogs are generated inside a disposable local directory.
Never downloads, collects, accesses TeraBox or writes production indexes.
"""
from __future__ import annotations
import json
import tempfile
from pathlib import Path

from merge_incremental import merge
from test_incremental import catalog, photo


def validate(model: str) -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        previous_photo = photo("test-album", 1, model + "-saved")
        incoming_photo = photo("test-album", 2, model + "-new")
        previous = root / "old.json"
        previous.write_text(json.dumps(catalog(model, [previous_photo])), encoding="utf-8")
        stage = root / "stage"
        (stage / "metadata").mkdir(parents=True)
        source = stage / "metadata" / "catalog.json"
        source.write_text(json.dumps(catalog(model, [incoming_photo])), encoding="utf-8")
        result = merge(stage, previous, model)
        final = json.loads(source.read_text(encoding="utf-8"))
        output = final["albums"][0]["images"]
        assert [p["number"] for p in output] == [1, 2], result
        assert output[0]["sha256"] == previous_photo["sha256"]
        assert output[1]["sha256"] == incoming_photo["sha256"]
        assert result["previous_photos"] == 1 and result["new_photos"] == 1
        assert result["total_photos"] == 2

        # A forged higher pixel count in an existing slot is NOT an optical
        # proof and must not replace the owner's previously verified original.
        altered = photo("test-album", 1, model + "-unproven-upscale", pixels=6000)
        forged = root / "forged"
        (forged / "metadata").mkdir(parents=True)
        forged_catalog = forged / "metadata" / "catalog.json"
        forged_catalog.write_text(json.dumps(catalog(model, [altered])), encoding="utf-8")
        blocked = merge(forged, previous, model)
        after = json.loads(forged_catalog.read_text(encoding="utf-8"))
        assert after["albums"][0]["images"][0]["sha256"] == previous_photo["sha256"]
        assert blocked["upgraded_photos"] == 0 and blocked["lower_quality_rejected"] == 1
        print("GALLERY_INCREMENTAL_SAVED_ORIGINALS_PRESERVED", model)


if __name__ == "__main__":
    for model_name in ("yui", "mimmi"):
        validate(model_name)
