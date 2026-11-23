import SwiftUI

struct PlayerBar: View {
    @EnvironmentObject private var player: PlayerService

    var body: some View {
        if let current = player.current {
            HStack(spacing: 12) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(current.title)
                        .font(.subheadline.weight(.semibold))
                        .lineLimit(1)
                    Text(current.artistLine)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }
                Spacer()
                Button { player.previous() } label: {
                    Image(systemName: "backward.fill")
                }
                Button { player.toggle() } label: {
                    Image(systemName: player.isPlaying ? "pause.fill" : "play.fill")
                }
                Button { player.next() } label: {
                    Image(systemName: "forward.fill")
                }
            }
            .padding(.horizontal)
            .padding(.vertical, 10)
            .background(.ultraThinMaterial)
            .buttonStyle(.borderless)
        }
    }
}
