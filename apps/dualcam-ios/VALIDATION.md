# Validation

Version: **1.0.1 (build 2)**

Source commit: `49696bbb4a0df73da2c8e7331fe85416b320d79c`

Successful run: https://github.com/koith/browser-app-lab/actions/runs/40372915486

Environment: GitHub-hosted macOS 15, Xcode 16.4, iPhoneOS 18.5 SDK; minimum iOS 16.0.

## Passed

- Swift syntax parsing for all 13 app/test source files.
- Deterministic Xcode project regeneration and resolution of all 57 project objects.
- Info.plist, shared scheme, asset catalog, Bash/Python scripts, and monorepo workflow paths.
- Simulator compilation of the app and test target.
- Eleven XCTest cases, with zero failures:
  - Two output movies both contain video and at least 1.8 seconds of decoded audio from a 2-second microphone input.
  - Stopping before the second camera is ready does not report success.
  - Both cameras use the later first-frame timestamp as their common origin.
  - Each camera accepts monotonically increasing frames independently.
  - Invalid times and repeated starts cannot alter the common origin.
  - Temporary encoder backpressure preserves queued audio in order.
  - Buffer overflow reports an error without replacing queued audio.
  - Failed appends do not consume unwritten audio samples.
  - Startup permits warmup, then detects a missing microphone.
  - A frozen rear camera is detected while the other streams continue.
  - Repeated and invalid timestamps cannot keep a dead stream healthy.
- Release build for a physical iPhone target (`BUILD SUCCEEDED`).
- IPA creation and GitHub Actions artifact upload.
- The IPA packager verifies that a compiled device executable exists and that Info.plist identifies an iPhoneOS build, and refuses to package a simulator app.

Artifact ZIP SHA-256 reported by GitHub: `1f0bc4020052a6b33d6b9646c2552789cb4f8463ce4d1ca809de58a6cbbb35b2`

Artifact: https://github.com/koith/browser-app-lab/actions/runs/40372915486/artifacts/12672959508

This version's artifact has not been independently downloaded and inspected locally. The build, packaging, and test results above are from the successful GitHub Actions run.

## Remaining device checks

The IPA has not been signed or installed on a physical iPhone in this session. Camera hardware compatibility, simultaneous real camera capture, actual start/stop sound behavior, brightness restoration, lock/interruption file saving, long-duration audio sync, dropped frames, and thermal behavior require the user's iPhone. No app-generated recording sounds are present, but regional/system behavior has not been verified.

Xcode emitted Swift concurrency migration warnings for serial-queue captures while compiling in Swift 5 mode; tests and both build targets passed. This is not a Swift 6 strict-concurrency migration.
