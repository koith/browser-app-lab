#!/usr/bin/env python3
"""Package a genuine Xcode device build; this never fabricates a binary."""
from pathlib import Path
import plistlib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "build/DerivedData/Build/Products/Release-iphoneos/DualCam.app"
if not (APP / "DualCam").is_file():
    raise SystemExit("No compiled iPhone app found. Run build_unsigned.sh on macOS first.")
with (APP / "Info.plist").open("rb") as file:
    info = plistlib.load(file)
if info.get("DTPlatformName") != "iphoneos":
    raise SystemExit("Refusing to package a simulator app for an iPhone.")

destination = ROOT / "build/DualCam-unsigned.ipa"
with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(APP.rglob("*")):
        if path.is_file():
            archive.write(path, "Payload/DualCam.app/" + path.relative_to(APP).as_posix())
print(f"Created {destination.name}; sign with AltStore Classic or Sideloadly before installation.")
