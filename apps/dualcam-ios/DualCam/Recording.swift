import Foundation

struct Recording: Identifiable, Codable {
    let id: UUID
    let createdAt: Date
    let duration: TimeInterval

    var folder: URL { RecordingStore.root.appendingPathComponent(id.uuidString, isDirectory: true) }
    var rearURL: URL { folder.appendingPathComponent("rear.mov") }
    var frontURL: URL { folder.appendingPathComponent("front.mov") }
}

enum RecordingStore {
    static var root: URL {
        FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("Recordings", isDirectory: true)
    }

    static func createFolder(id: UUID) throws -> URL {
        let folder = root.appendingPathComponent(id.uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        // Keep large, local-only recordings out of iCloud device backups.
        var excluded = root
        var values = URLResourceValues()
        values.isExcludedFromBackup = true
        try excluded.setResourceValues(values)
        return folder
    }

    static func save(_ recording: Recording) throws {
        let data = try JSONEncoder().encode(recording)
        try data.write(to: recording.folder.appendingPathComponent("recording.json"), options: .atomic)
    }

    static func load() -> [Recording] {
        let folders = (try? FileManager.default.contentsOfDirectory(
            at: root, includingPropertiesForKeys: nil, options: .skipsHiddenFiles
        )) ?? []
        return folders.compactMap { folder -> Recording? in
            guard let data = try? Data(contentsOf: folder.appendingPathComponent("recording.json")),
                  let item = try? JSONDecoder().decode(Recording.self, from: data),
                  item.folder.standardizedFileURL == folder.standardizedFileURL,
                  FileManager.default.fileExists(atPath: item.rearURL.path),
                  FileManager.default.fileExists(atPath: item.frontURL.path) else { return nil }
            return item
        }.sorted { $0.createdAt > $1.createdAt }
    }

    static func delete(_ recording: Recording) throws {
        try FileManager.default.removeItem(at: recording.folder)
    }

    static func freeBytes() -> Int64 {
        let attributes = try? FileManager.default.attributesOfFileSystem(forPath: NSHomeDirectory())
        return (attributes?[.systemFreeSize] as? NSNumber)?.int64Value ?? 0
    }
}

enum RecorderError: LocalizedError {
    case message(String)
    var errorDescription: String? {
        switch self { case .message(let text): return text }
    }
}
