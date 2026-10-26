import AVFoundation
import SwiftUI

struct ContentView: View {
    @StateObject private var capture = CaptureController()
    @StateObject private var blackout = BlackoutController()
    @Environment(\.scenePhase) private var scenePhase
    @State private var showsLibrary = false

    private var recording: Bool { capture.state == .recording || capture.state == .starting }
    private var busy: Bool { capture.state == .preparing || capture.state == .saving }
    private let accent = Color(red: 0.49, green: 0.94, blue: 0.77)

    var body: some View {
        ZStack {
            Color(red: 0.035, green: 0.045, blue: 0.055).ignoresSafeArea()
            VStack(spacing: 18) {
                header
                preview
                VStack(spacing: 14) {
                    HStack(spacing: 8) {
                        Circle().fill(recording ? Color.red : accent).frame(width: 7, height: 7)
                        Text(capture.status).font(.caption).foregroundStyle(.secondary)
                            .lineLimit(2).multilineTextAlignment(.center)
                    }
                    controls
                    Text(recording ? "검은 화면에서는 두 번 탭하면 조작 화면으로 돌아옵니다." : "전·후면 각각 저장 · 음성 포함 · 앱 효과음 없음")
                        .font(.caption2).foregroundStyle(.secondary).multilineTextAlignment(.center)
                }
            }
            .padding(.horizontal, 20).padding(.top, 10).padding(.bottom, 16)
            .accessibilityHidden(blackout.isActive)

            if blackout.isActive {
                Color.black.ignoresSafeArea()
                    .contentShape(Rectangle())
                    .onTapGesture(count: 2) { blackout.exit() }
                    .accessibilityLabel("녹화 중. 조작 화면 열기")
                    .accessibilityAddTraits(.isButton)
                    .accessibilityAction { blackout.exit() }
            }
        }
        .statusBarHidden(blackout.isActive)
        .persistentSystemOverlays(blackout.isActive ? .hidden : .automatic)
        .task { await capture.prepare() }
        .onChange(of: capture.state) { state in
            UIApplication.shared.isIdleTimerDisabled = [.starting, .recording, .saving].contains(state)
            if state != .recording && state != .starting { blackout.exit() }
        }
        .onChange(of: scenePhase) { phase in
            if phase == .active { capture.resume() }
            else {
                blackout.exit()
                UIApplication.shared.isIdleTimerDisabled = false
                capture.suspend()
            }
        }
        .onDisappear {
            blackout.exit()
            UIApplication.shared.isIdleTimerDisabled = false
        }
        .sheet(isPresented: $showsLibrary) { RecordingLibrary(capture: capture) }
        .alert("알림", isPresented: Binding(
            get: { capture.errorMessage != nil },
            set: { if !$0 { capture.errorMessage = nil } }
        ), actions: {
            Button("확인", role: .cancel) { capture.errorMessage = nil }
        }, message: { Text(capture.errorMessage ?? "") })
    }

    private var header: some View {
        HStack(alignment: .center) {
            VStack(alignment: .leading, spacing: 3) {
                Text("DUALCAM").font(.system(size: 23, weight: .bold, design: .rounded)).tracking(3)
                Text("두 시선, 하나의 순간").font(.caption).foregroundStyle(.secondary)
            }
            Spacer()
            if let startedAt = capture.startedAt, recording {
                HStack(spacing: 7) {
                    Circle().fill(.red).frame(width: 7, height: 7)
                    Text(startedAt, style: .timer).monospacedDigit().font(.system(.body, design: .monospaced))
                }.foregroundStyle(.white)
            } else {
                Text("DUAL / AUDIO").font(.system(size: 10, weight: .semibold, design: .monospaced))
                    .foregroundStyle(accent).padding(9)
                    .overlay(Capsule().stroke(accent.opacity(0.3)))
            }
        }
    }

    private var preview: some View {
        ZStack(alignment: .topTrailing) {
            CameraPreview(previewLayer: capture.rearPreview)
            if capture.state == .unavailable || capture.state == .preparing {
                Color.black.opacity(0.85)
                VStack(spacing: 16) {
                    if capture.state == .preparing { ProgressView().tint(accent) }
                    else { Image(systemName: "camera.fill").font(.largeTitle).foregroundStyle(accent) }
                    Text(capture.status).font(.callout).multilineTextAlignment(.center)
                    if capture.state == .unavailable {
                        HStack {
                            Button("설정 열기") {
                                if let url = URL(string: UIApplication.openSettingsURLString) {
                                    UIApplication.shared.open(url)
                                }
                            }
                            Button("재시도") { capture.retry() }
                        }.buttonStyle(.bordered)
                    }
                }.padding(28).frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                CameraPreview(previewLayer: capture.frontPreview)
                    .frame(width: 106, height: 156)
                    .overlay(alignment: .bottomLeading) { cameraLabel("FRONT").padding(8) }
                    .clipShape(RoundedRectangle(cornerRadius: 14))
                    .overlay(RoundedRectangle(cornerRadius: 14).stroke(.white.opacity(0.25)))
                    .padding(14)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(.black)
        .overlay(alignment: .bottomLeading) { cameraLabel("REAR").padding(14) }
        .clipShape(RoundedRectangle(cornerRadius: 24))
        .overlay(RoundedRectangle(cornerRadius: 24).stroke(.white.opacity(0.10)))
    }

    private func cameraLabel(_ text: String) -> some View {
        Text(text).font(.system(size: 9, weight: .bold, design: .monospaced)).tracking(2)
            .padding(.horizontal, 8).padding(.vertical, 5)
            .background(.black.opacity(0.55), in: Capsule())
    }

    private var controls: some View {
        HStack(spacing: 0) {
            Button {
                capture.refreshRecordings()
                showsLibrary = true
            } label: {
                VStack(spacing: 7) {
                    Image(systemName: "rectangle.stack").font(.system(size: 23))
                    Text("녹화 목록").font(.caption2)
                }.frame(maxWidth: .infinity)
            }.disabled(recording || busy)

            Button {
                if recording { capture.stopRecording() } else { capture.startRecording() }
            } label: {
                ZStack {
                    Circle().stroke(.white.opacity(0.8), lineWidth: 3).frame(width: 78, height: 78)
                    if busy { ProgressView().tint(.white) }
                    else if recording {
                        RoundedRectangle(cornerRadius: 7).fill(.red).frame(width: 29, height: 29)
                    } else { Circle().fill(.red).frame(width: 64, height: 64) }
                }
            }
            .accessibilityLabel(recording ? "녹화 종료" : "전·후면 녹화 시작")
            .disabled(busy || capture.state == .unavailable)

            Button { blackout.enter() } label: {
                VStack(spacing: 7) {
                    Image(systemName: "moon.fill").font(.system(size: 23))
                    Text("검은 화면").font(.caption2)
                }.frame(maxWidth: .infinity)
            }.disabled(capture.state != .recording)
        }
        .tint(accent)
        .buttonStyle(.plain)
    }
}

private final class BlackoutController: ObservableObject {
    @Published private(set) var isActive = false
    private var previousBrightness: CGFloat?

    func enter() {
        guard !isActive else { return }
        previousBrightness = UIScreen.main.brightness
        UIScreen.main.brightness = 0
        isActive = true
    }

    func exit() {
        guard isActive else { return }
        if let previousBrightness { UIScreen.main.brightness = previousBrightness }
        previousBrightness = nil
        isActive = false
    }
}

private struct CameraPreview: UIViewRepresentable {
    let previewLayer: AVCaptureVideoPreviewLayer
    func makeUIView(context: Context) -> PreviewContainer { PreviewContainer(previewLayer) }
    func updateUIView(_ uiView: PreviewContainer, context: Context) {}
}

private final class PreviewContainer: UIView {
    private let preview: AVCaptureVideoPreviewLayer
    init(_ preview: AVCaptureVideoPreviewLayer) {
        self.preview = preview
        super.init(frame: .zero)
        backgroundColor = .black
        layer.addSublayer(preview)
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }
    override func layoutSubviews() {
        super.layoutSubviews()
        CATransaction.begin()
        CATransaction.setDisableActions(true)
        preview.frame = bounds
        CATransaction.commit()
    }
}
