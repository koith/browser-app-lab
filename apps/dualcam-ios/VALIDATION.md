# Validation

Source commit: `233634e93be9bb6459506dca3c95037dad9cfbf8`

Successful run: https://github.com/koith/browser-app-lab/actions/runs/40368695687

Environment: GitHub-hosted macOS 15, Xcode 16.4, iPhoneOS 18.5 SDK; minimum iOS 16.0.

## Passed

- Swift syntax parsing for all 9 app/test source files.
- Deterministic Xcode project regeneration and resolution of all 47 project objects.
- Info.plist, shared scheme, asset catalog, Bash/Python scripts, and monorepo workflow paths.
- Simulator compilation of the app and test target.
- Five XCTest cases, with zero failures:
  - Two output movies both contain video and decodable AAC audio.
  - Stopping before the second camera is ready does not report success.
  - Both cameras use the later first-frame timestamp as their common origin.
  - Each camera accepts monotonically increasing frames independently.
  - Invalid times and repeated starts cannot alter the common origin.
- Release build for a physical iPhone target (`BUILD SUCCEEDED`).
- IPA creation and GitHub Actions artifact upload.
- Downloaded artifact SHA-256 matches GitHub's artifact digest; ZIP CRC checks pass.
- IPA contains a genuine arm64 Mach-O executable and an iPhoneOS Info.plist, with both camera and microphone permission descriptions.

IPA SHA-256: `2966d288d1a197b7e9a83a1934da25a544ebd74332416f680cd7537b4a585dd5`

Artifact: https://github.com/koith/browser-app-lab/actions/runs/40368695687/artifacts/12672616233

## Remaining device checks

The IPA has not been signed or installed on a physical iPhone in this session. Camera hardware compatibility, simultaneous real camera capture, actual start/stop sound behavior, brightness restoration, lock/interruption file saving, long-duration audio sync, dropped frames, and thermal behavior require the user's iPhone. No app-generated recording sounds are present, but regional/system behavior has not been verified.

Xcode emitted Swift concurrency migration warnings for serial-queue captures while compiling in Swift 5 mode; tests and both build targets passed. This is not a Swift 6 strict-concurrency migration.
