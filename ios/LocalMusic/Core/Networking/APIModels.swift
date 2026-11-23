import Foundation

extension JSONDecoder {
    static let api: JSONDecoder = {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return decoder
    }()
}

extension JSONEncoder {
    static let api: JSONEncoder = {
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        return encoder
    }()
}

struct TokenResponse: Codable, Equatable {
    let accessToken: String
    let refreshToken: String
    let expiresIn: Int
    let tokenType: String
}

struct UserProfile: Codable, Equatable, Identifiable {
    let id: String
    let email: String
    let username: String
    let role: String
    let isMaster: Bool
    let isActive: Bool
    let createdAt: String
}

struct ArtistRef: Codable, Equatable, Identifiable {
    let id: String
    let name: String
}

struct AlbumRef: Codable, Equatable, Identifiable {
    let id: String
    let title: String
    let releaseYear: Int?
}

enum TrackStatus: String, Codable {
    case downloading
    case ready
    case failed
    case blocked
    case unrecoverable
}

struct TrackSummary: Codable, Equatable, Identifiable {
    let id: String
    let title: String
    let durationSeconds: Int?
    let status: TrackStatus
    let playCount: Int
    let hasLyrics: Bool
    let artists: [ArtistRef]
    let album: AlbumRef?
    let unverified: Bool
    let userSentiment: String?

    var artistLine: String {
        artists.map(\.name).joined(separator: ", ")
    }
}

struct TrackListResponse: Codable, Equatable {
    let items: [TrackSummary]
    let page: Int
    let pageSize: Int
    let total: Int
}

struct PlaylistSummary: Codable, Equatable, Identifiable {
    let id: String
    let name: String
    let isFavourite: Bool
    let isPublic: Bool
    let trackCount: Int
    let createdAt: String
}

struct PlaylistTrackItem: Codable, Equatable, Identifiable {
    let track: TrackSummary
    let position: Int
    let addedAt: String

    var id: String { track.id }
}

struct PlaylistDetail: Codable, Equatable, Identifiable {
    let id: String
    let name: String
    let isFavourite: Bool
    let isPublic: Bool
    let trackCount: Int
    let createdAt: String
    let tracks: [PlaylistTrackItem]
}

struct LoginBody: Encodable {
    let login: String
    let password: String
}

struct RefreshBody: Encodable {
    let refreshToken: String
}

struct LogoutBody: Encodable {
    let refreshToken: String
}

struct CreatePlaylistBody: Encodable {
    let name: String
    let isPublic: Bool
}

struct APIProblem: Codable {
    let title: String?
    let status: Int?
    let detail: String?
}

struct APIFailure: Error, LocalizedError {
    let status: Int
    let detail: String

    var errorDescription: String? { detail }
}
