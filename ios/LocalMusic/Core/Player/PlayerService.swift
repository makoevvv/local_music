import AVFoundation
import Combine
import MediaPlayer

@MainActor
final class PlayerService: ObservableObject {
    @Published private(set) var current: TrackSummary?
    @Published private(set) var isPlaying = false

    private let player = AVPlayer()
    private var queue: [TrackSummary] = []
    private var index = 0
    private var baseURL: URL?
    private var token = ""
    private var endObserver: NSObjectProtocol?
    private var timeObserver: Any?

    init() {
        let session = AVAudioSession.sharedInstance()
        try? session.setCategory(.playback, mode: .default)
        try? session.setActive(true)
        player.actionAtItemEnd = .pause
        timeObserver = player.addPeriodicTimeObserver(
            forInterval: CMTime(seconds: 1, preferredTimescale: 1),
            queue: .main
        ) { [weak self] time in
            Task { @MainActor in
                self?.publishPlayback(time)
            }
        }
        let commands = MPRemoteCommandCenter.shared()
        commands.playCommand.addTarget { [weak self] _ in
            Task { @MainActor in self?.resume() }
            return .success
        }
        commands.pauseCommand.addTarget { [weak self] _ in
            Task { @MainActor in self?.pause() }
            return .success
        }
        commands.nextTrackCommand.addTarget { [weak self] _ in
            Task { @MainActor in self?.next() }
            return .success
        }
        commands.previousTrackCommand.addTarget { [weak self] _ in
            Task { @MainActor in self?.previous() }
            return .success
        }
    }

    func play(tracks: [TrackSummary], startAt start: Int, baseURL: URL, token: String) {
        let playable = tracks.filter { $0.status == .ready }
        guard !playable.isEmpty else { return }
        queue = playable
        self.baseURL = baseURL
        self.token = token
        let wanted = tracks[safe: start]?.id
        index = playable.firstIndex { $0.id == wanted } ?? 0
        startCurrent()
    }

    func toggle() {
        if isPlaying {
            pause()
        } else {
            resume()
        }
    }

    func resume() {
        player.play()
        isPlaying = current != nil
        publishPlayback(player.currentTime())
    }

    func pause() {
        player.pause()
        isPlaying = false
        publishPlayback(player.currentTime())
    }

    func next() {
        guard index + 1 < queue.count else {
            pause()
            return
        }
        index += 1
        startCurrent()
    }

    func previous() {
        if player.currentTime().seconds > 3 {
            player.seek(to: .zero)
            resume()
            return
        }
        guard index > 0 else {
            player.seek(to: .zero)
            return
        }
        index -= 1
        startCurrent()
    }

    private func startCurrent() {
        guard let baseURL, queue.indices.contains(index) else { return }
        let track = queue[index]
        guard let url = URL(string: baseURL.absoluteString.trimmingCharacters(in: CharacterSet(charactersIn: "/")) + "/api/v1/tracks/\(track.id)/stream") else {
            return
        }
        let asset = AVURLAsset(
            url: url,
            options: ["AVURLAssetHTTPHeaderFieldsKey": ["Authorization": "Bearer \(token)"]]
        )
        let item = AVPlayerItem(asset: asset)
        observeEnd(of: item)
        current = track
        player.replaceCurrentItem(with: item)
        resume()
    }

    private func observeEnd(of item: AVPlayerItem) {
        if let endObserver {
            NotificationCenter.default.removeObserver(endObserver)
        }
        endObserver = NotificationCenter.default.addObserver(
            forName: .AVPlayerItemDidPlayToEndTime,
            object: item,
            queue: .main
        ) { [weak self] _ in
            Task { @MainActor in self?.next() }
        }
    }

    private func publishPlayback(_ time: CMTime) {
        guard let current else { return }
        var info: [String: Any] = [
            MPMediaItemPropertyTitle: current.title,
            MPMediaItemPropertyArtist: current.artistLine,
            MPNowPlayingInfoPropertyElapsedPlaybackTime: time.seconds.isFinite ? time.seconds : 0,
            MPNowPlayingInfoPropertyPlaybackRate: isPlaying ? 1.0 : 0.0,
        ]
        if let duration = current.durationSeconds {
            info[MPMediaItemPropertyPlaybackDuration] = duration
        }
        MPNowPlayingInfoCenter.default().nowPlayingInfo = info
    }
}

private extension Array {
    subscript(safe index: Int) -> Element? {
        indices.contains(index) ? self[index] : nil
    }
}
