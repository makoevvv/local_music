import SwiftUI

struct CatalogView: View {
    @EnvironmentObject private var session: SessionStore
    @EnvironmentObject private var player: PlayerService
    @State private var tracks: [TrackSummary] = []
    @State private var query = ""
    @State private var errorMessage: String?
    @State private var isLoading = false

    var body: some View {
        NavigationStack {
            List(tracks) { track in
                Button {
                    play(track)
                } label: {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(track.title)
                            .foregroundStyle(.primary)
                        Text(track.artistLine.isEmpty ? "Unknown artist" : track.artistLine)
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                }
            }
            .overlay {
                if isLoading && tracks.isEmpty {
                    ProgressView()
                } else if tracks.isEmpty {
                    Text(errorMessage ?? "No tracks")
                        .foregroundStyle(.secondary)
                }
            }
            .navigationTitle("Catalog")
            .searchable(text: $query, prompt: "Search")
            .onSubmit(of: .search) { Task { await load() } }
            .refreshable { await load() }
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Sign out") { Task { await session.signOut() } }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Play") { play(tracks.first) }
                        .disabled(tracks.isEmpty)
                }
            }
            .task { await load() }
        }
    }

    private func load() async {
        guard let baseURL = session.baseURL else { return }
        isLoading = true
        defer { isLoading = false }
        do {
            let page = try await session.client.tracks(baseURL: baseURL, query: query, page: 1)
            tracks = page.items
            errorMessage = nil
        } catch {
            errorMessage = (error as? LocalizedError)?.errorDescription ?? "Could not load tracks"
        }
    }

    private func play(_ track: TrackSummary?) {
        guard let track, let baseURL = session.baseURL, let token = session.accessToken else { return }
        let start = tracks.firstIndex { $0.id == track.id } ?? 0
        player.play(tracks: tracks, startAt: start, baseURL: baseURL, token: token)
        Task { await session.client.logPlay(baseURL: baseURL, trackID: track.id) }
    }
}
