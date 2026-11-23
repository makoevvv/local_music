import SwiftUI

@main
struct LocalMusicApp: App {
    @StateObject private var session = SessionStore()
    @StateObject private var player = PlayerService()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(session)
                .environmentObject(player)
                .task { await session.restore() }
        }
    }
}
