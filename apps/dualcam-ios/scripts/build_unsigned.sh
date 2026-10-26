#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v xcodebuild >/dev/null 2>&1; then
  echo "This script needs macOS and Xcode. Run the GitHub Actions workflow instead."
  exit 1
fi

python3 scripts/generate_project.py
mkdir -p build
xcodebuild \
  -project DualCam.xcodeproj -scheme DualCam -configuration Release \
  -sdk iphoneos -destination 'generic/platform=iOS' \
  -derivedDataPath build/DerivedData \
  CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO \
  build | tee build/device-build.log

python3 scripts/package_ipa.py
