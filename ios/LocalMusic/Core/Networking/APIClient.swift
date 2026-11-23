import Foundation

actor APIClient {
    private let session: URLSession
    private var accessToken: String?
    private var refreshToken: String?
    private var onTokensUpdated: (@Sendable (TokenResponse) -> Void)?

    init(session: URLSession = .shared) {
        self.session = session
    }

    func setTokenHandler(_ handler: @escaping @Sendable (TokenResponse) -> Void) {
        onTokensUpdated = handler
    }

    func updateTokens(access: String?, refresh: String?) {
        accessToken = access
        refreshToken = refresh
    }

    func login(baseURL: URL, login: String, password: String) async throws -> TokenResponse {
        let tokens: TokenResponse = try await send(
            baseURL: baseURL,
            path: "/api/v1/auth/login",
            method: "POST",
            body: LoginBody(login: login, password: password),
            authorize: false
        )
        remember(tokens)
        return tokens
    }

    func refresh(baseURL: URL) async throws -> TokenResponse {
        guard let refreshToken else {
            throw APIFailure(status: 401, detail: "Not signed in")
        }
        let tokens: TokenResponse = try await send(
            baseURL: baseURL,
            path: "/api/v1/auth/refresh",
            method: "POST",
            body: RefreshBody(refreshToken: refreshToken),
            authorize: false
        )
        remember(tokens)
        return tokens
    }

    private func remember(_ tokens: TokenResponse) {
        accessToken = tokens.accessToken
        refreshToken = tokens.refreshToken
        onTokensUpdated?(tokens)
    }

    func logout(baseURL: URL) async {
        guard let refreshToken else { return }
        let _: EmptyBody = (try? await send(
            baseURL: baseURL,
            path: "/api/v1/auth/logout",
            method: "POST",
            body: LogoutBody(refreshToken: refreshToken),
            authorize: false
        )) ?? EmptyBody()
    }

    func me(baseURL: URL) async throws -> UserProfile {
        try await send(baseURL: baseURL, path: "/api/v1/auth/me")
    }

    func tracks(baseURL: URL, query: String, page: Int) async throws -> TrackListResponse {
        var items = [
            URLQueryItem(name: "page", value: String(page)),
            URLQueryItem(name: "page_size", value: "50"),
        ]
        if !query.isEmpty {
            items.append(URLQueryItem(name: "q", value: query))
        }
        return try await send(baseURL: baseURL, path: "/api/v1/tracks", query: items)
    }

    func playlists(baseURL: URL) async throws -> [PlaylistSummary] {
        try await send(baseURL: baseURL, path: "/api/v1/playlists")
    }

    func playlist(baseURL: URL, id: String) async throws -> PlaylistDetail {
        try await send(baseURL: baseURL, path: "/api/v1/playlists/\(id)")
    }

    func createPlaylist(baseURL: URL, name: String) async throws -> PlaylistSummary {
        try await send(
            baseURL: baseURL,
            path: "/api/v1/playlists",
            method: "POST",
            body: CreatePlaylistBody(name: name, isPublic: false)
        )
    }

    func logPlay(baseURL: URL, trackID: String) async {
        let _: PlayStartResponse? = try? await send(
            baseURL: baseURL,
            path: "/api/v1/tracks/\(trackID)/play",
            method: "POST"
        )
    }

    func streamURL(baseURL: URL, trackID: String) -> URL? {
        endpoint(baseURL: baseURL, path: "/api/v1/tracks/\(trackID)/stream", query: [])
    }

    private func send<Response: Decodable>(
        baseURL: URL,
        path: String,
        method: String = "GET",
        query: [URLQueryItem] = [],
        body: (any Encodable)? = nil,
        authorize: Bool = true,
        allowRefresh: Bool = true
    ) async throws -> Response {
        guard let url = endpoint(baseURL: baseURL, path: path, query: query) else {
            throw APIFailure(status: 0, detail: "Server URL is invalid")
        }
        var request = URLRequest(url: url)
        request.httpMethod = method
        if let body {
            request.httpBody = try JSONEncoder.api.encode(AnyEncodable(body))
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        if authorize, let accessToken {
            request.setValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")
        }

        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw APIFailure(status: 0, detail: "No response from server")
        }
        if http.statusCode == 401, authorize, allowRefresh, refreshToken != nil {
            let tokens = try await refresh(baseURL: baseURL)
            updateTokens(access: tokens.accessToken, refresh: tokens.refreshToken)
            return try await send(
                baseURL: baseURL,
                path: path,
                method: method,
                query: query,
                body: body,
                authorize: authorize,
                allowRefresh: false
            )
        }
        guard (200 ..< 300).contains(http.statusCode) else {
            let problem = try? JSONDecoder.api.decode(APIProblem.self, from: data)
            throw APIFailure(
                status: http.statusCode,
                detail: problem?.detail ?? problem?.title ?? "Request failed (\(http.statusCode))"
            )
        }
        if data.isEmpty || Response.self == EmptyBody.self {
            return EmptyBody() as! Response
        }
        do {
            return try JSONDecoder.api.decode(Response.self, from: data)
        } catch {
            throw APIFailure(status: http.statusCode, detail: "Could not read the server response")
        }
    }

    private func endpoint(baseURL: URL, path: String, query: [URLQueryItem]) -> URL? {
        let trimmed = baseURL.absoluteString.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        guard var components = URLComponents(string: trimmed + path) else { return nil }
        if !query.isEmpty {
            components.queryItems = query
        }
        return components.url
    }
}

private struct EmptyBody: Codable {}

private struct PlayStartResponse: Codable {
    let playId: Int
}

private struct AnyEncodable: Encodable {
    private let encodeBody: (Encoder) throws -> Void

    init(_ wrapped: any Encodable) {
        encodeBody = { encoder in
            try wrapped.encode(to: encoder)
        }
    }

    func encode(to encoder: Encoder) throws {
        try encodeBody(encoder)
    }
}
