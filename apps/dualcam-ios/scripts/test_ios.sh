#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/generate_project.py
mkdir -p build
xcrun simctl list devices available --json > build/simulators.json
device_id=$(python3 - <<'PY'
import json
from pathlib import Path
data = json.loads(Path("build/simulators.json").read_text())
for runtime, devices in sorted(data["devices"].items(), reverse=True):
    if ".iOS-" not in runtime:
        continue
    for device in devices:
        if device.get("isAvailable") and "iPhone" in device["name"]:
            print(device["udid"])
            raise SystemExit(0)
raise SystemExit("No available iPhone simulator runtime")
PY
)
xcodebuild \
  -project DualCam.xcodeproj -scheme DualCam -configuration Debug \
  -destination "platform=iOS Simulator,id=$device_id" \
  -derivedDataPath build/TestDerivedData \
  -resultBundlePath "build/Tests-$(date +%s).xcresult" \
  -parallel-testing-enabled NO \
  CODE_SIGNING_ALLOWED=NO \
  test | tee build/tests.log
