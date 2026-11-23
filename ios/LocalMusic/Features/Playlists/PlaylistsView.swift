import SwiftUI

struct PlaylistsView: View {
    @EnvironmentObject private var session: SessionStore
    @State private var playlists: [PlaylistSummary] = []
    @State private var errorMessage: String?
    @State private var newName = ""

    var body: some View {
        NavigationStack {
            List {
                Section("New playlist") {
                    TextField("Name", text: $newName)
                    Button("Create") { Task { await create() } }
                        .disabled(newName.trimmingCharacters(in: .whitespaces).isEmpty)
                }
                Section("Library") {
                    ForEach(playlists) { playlist in
                        NavigationLink {
                            PlaylistDetailView(playlistID: playlist.id, title: playlist.name)
                        } label: {
                            VStack(alignment: .leading) {
                                Text(playlist.name)
                                Text("\(playlist.trackCount) tracks")
                                    .font(.subheadline)
                                    .foregroundStyle(.secondary)
                            }
                        }
                    }
                }
            }
            .overlay {
                if let errorMessage, playlists.isEmpty {
                    Text(errorMessage).foregroundStyle(.secondary)
                }
            }
            .navigationTitle("Playlists")
            .refreshable { await load() }
            .task { await load() }
        }
    }

    private func load() async {
        guard let baseURL = session.baseURL else { return }
        do {
            playlists = try await session.client.playlists(baseURL: baseURL)
            errorMessage = nil
        } catch {
            errorMessage = (error as? LocalizedError)?.errorDescription ?? "Could not load playlists"
        }
    }

    private func create() async {
        guard let baseURL = session.baseURL else { return }
        let name = newName.trimmingCharacters(in: .whitespaces)
        guard !name.isEmpty else { return }
        do {
            _ = try await session.client.createPlaylist(baseURL: baseURL, name: name)
            newName = ""
            await load()
        } catch {
            errorMessage = (error as? LocalizedError)?.errorDescription ?? "Could not create playlist"
        }
    }
}

struct PlaylistDetailView: View {
    @EnvironmentObject private var session: SessionStore
    @EnvironmentObject private var player: PlayerService
    let playlistID: String
    let title: String
    @State private var tracks: [TrackSummary] = []
    @State private var errorMessage: String?

    var body: some View {
        List(tracks) { track in
            Button {
                play(track)
            } label: {
                VStack(alignment: .leading, spacing: 2) {
                    Text(track.title).foregroundStyle(.primary)
                    Text(track.artistLine.isEmpty ? "Unknown artist" : track.artistLine)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .navigationTitle(title)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button("Play") { play(tracks.first) }
                    .disabled(tracks.isEmpty)
            }
        }
        .overlay {
            if let errorMessage, tracks.isEmpty {
                Text(errorMessage).foregroundStyle(.secondary)
            }
        }
        .task { await load() }
    }

    private func load() async {
        guard let baseURL = session.baseURL else { return }
        do {
            let detail = try await session.client.playlist(baseURL: baseURL, id: playlistID)
            tracks = detail.tracks.map(\.track)
            errorMessage = nil
        } catch {
            errorMessage = (error as? LocalizedError)?.errorDescription ?? "Could not load playlist"
        }
    }

    private func play(_ track: TrackSummary?) {
        guard let track, let baseURL = session.baseURL, let token = session.accessToken else { return }
        let start = tracks.firstIndex { $0.id == track.id } ?? 0
        player.play(tracks: tracks, startAt: start, baseURL: baseURL, token: token)
        Task { await session.client.logPlay(baseURL: baseURL, trackID: track.id) }
    }
}
