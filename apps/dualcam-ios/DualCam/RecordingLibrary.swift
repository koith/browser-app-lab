import AVKit
import SwiftUI

struct RecordingLibrary: View {
    @ObservedObject var capture: CaptureController
    @Environment(\.dismiss) private var dismiss
    @State private var pendingDeletion: Recording?

    var body: some View {
        NavigationStack {
            Group {
                if capture.recordings.isEmpty {
                    VStack(spacing: 15) {
                        Image(systemName: "film.stack").font(.system(size: 44)).foregroundStyle(.secondary)
                        Text("아직 저장된 녹화가 없습니다.")
                        Text("영상은 파일 앱 → 나의 iPhone → DualCam에서도 볼 수 있습니다.")
                            .font(.caption).foregroundStyle(.secondary).multilineTextAlignment(.center)
                    }.padding(30)
                } else {
                    List(capture.recordings) { recording in
                        NavigationLink { RecordingDetail(recording: recording) } label: {
                            HStack(spacing: 14) {
                                Image(systemName: "video.badge.waveform.fill").font(.title2).foregroundStyle(.mint)
                                VStack(alignment: .leading, spacing: 5) {
                                    Text(recording.createdAt.formatted(date: .abbreviated, time: .shortened))
                                    Text("전면 + 후면 · 음성 포함 · \(Int(recording.duration))초")
                                        .font(.caption).foregroundStyle(.secondary)
                                }
                            }.padding(.vertical, 5)
                        }
                        .swipeActions {
                            Button(role: .destructive) { pendingDeletion = recording } label: {
                                Label("삭제", systemImage: "trash")
                            }
                        }
                    }
                }
            }
            .navigationTitle("녹화 목록")
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("완료") { dismiss() } } }
            .confirmationDialog("전면·후면 영상 두 개를 삭제할까요?", isPresented: Binding(
                get: { pendingDeletion != nil }, set: { if !$0 { pendingDeletion = nil } }
            ), titleVisibility: .visible) {
                Button("영상 삭제", role: .destructive) {
                    if let recording = pendingDeletion { capture.delete(recording) }
                    pendingDeletion = nil
                }
            }
        }
        .tint(.mint)
    }
}

private struct RecordingDetail: View {
    let recording: Recording
    @State private var side = 0
    @State private var player: AVPlayer?

    var body: some View {
        VStack(spacing: 20) {
            Picker("카메라", selection: $side) {
                Text("후면").tag(0)
                Text("전면").tag(1)
            }.pickerStyle(.segmented)
            VideoPlayer(player: player).clipShape(RoundedRectangle(cornerRadius: 16))
            HStack(spacing: 28) {
                ShareLink(item: recording.rearURL) { Label("후면 공유", systemImage: "square.and.arrow.up") }
                ShareLink(item: recording.frontURL) { Label("전면 공유", systemImage: "square.and.arrow.up") }
            }.font(.callout)
            Text("각 영상에 같은 마이크 음성이 포함됩니다.")
                .font(.caption).foregroundStyle(.secondary)
        }
        .padding(20)
        .navigationTitle("녹화 보기")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear { selectMovie() }
        .onChange(of: side) { _ in selectMovie() }
        .onDisappear { player?.pause(); player = nil }
    }

    private func selectMovie() {
        player?.pause()
        player = AVPlayer(url: side == 0 ? recording.rearURL : recording.frontURL)
    }
}
