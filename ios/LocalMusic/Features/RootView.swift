import SwiftUI

struct RootView: View {
    @EnvironmentObject private var session: SessionStore
    @EnvironmentObject private var player: PlayerService

    var body: some View {
        Group {
            if session.accessToken == nil {
                LoginView()
            } else {
                TabView {
                    CatalogView()
                        .tabItem { Label("Catalog", systemImage: "music.note.list") }
                    PlaylistsView()
                        .tabItem { Label("Playlists", systemImage: "list.bullet") }
                }
                .safeAreaInset(edge: .bottom) {
                    PlayerBar()
                }
            }
        }
        .environmentObject(player)
    }
}
