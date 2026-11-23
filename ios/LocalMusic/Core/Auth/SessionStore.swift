import Foundation

@MainActor
final class SessionStore: ObservableObject {
    @Published var serverText: String
    @Published var profile: UserProfile?
    @Published var accessToken: String?
    @Published var isBusy = false
    @Published var errorMessage: String?

    let client = APIClient()
    private let keychain = KeychainStore()
    private let accessKey = "access_token"
    private let refreshKey = "refresh_token"

    init() {
        serverText = UserDefaults.standard.string(forKey: "local_music_server_url") ?? "http://127.0.0.1:8000"
    }

    private func bindTokenHandler() async {
        await client.setTokenHandler { [weak self] tokens in
            Task { @MainActor in
                self?.apply(tokens)
            }
        }
    }

    var baseURL: URL? {
        URL(string: serverText.trimmingCharacters(in: .whitespacesAndNewlines))
    }

    func restore() async {
        let access = keychain.string(for: accessKey)
        let refresh = keychain.string(for: refreshKey)
        guard let baseURL, access != nil || refresh != nil else { return }
        await bindTokenHandler()
        await client.updateTokens(access: access, refresh: refresh)
        do {
            profile = try await client.me(baseURL: baseURL)
            accessToken = keychain.string(for: accessKey) ?? access
        } catch {
            await client.updateTokens(access: nil, refresh: nil)
            keychain.remove(accessKey)
            keychain.remove(refreshKey)
        }
    }

    func signIn(login: String, password: String) async {
        guard let baseURL, ["http", "https"].contains(baseURL.scheme) else {
            errorMessage = "Enter a server URL that starts with http:// or https://"
            return
        }
        isBusy = true
        errorMessage = nil
        defer { isBusy = false }
        await bindTokenHandler()
        do {
            let tokens = try await client.login(baseURL: baseURL, login: login, password: password)
            apply(tokens)
            UserDefaults.standard.set(baseURL.absoluteString, forKey: "local_music_server_url")
            serverText = baseURL.absoluteString
            profile = try await client.me(baseURL: baseURL)
        } catch {
            errorMessage = (error as? LocalizedError)?.errorDescription ?? "Sign in failed"
        }
    }

    func signOut() async {
        if let baseURL {
            await client.logout(baseURL: baseURL)
        }
        await client.updateTokens(access: nil, refresh: nil)
        keychain.remove(accessKey)
        keychain.remove(refreshKey)
        accessToken = nil
        profile = nil
    }

    private func apply(_ tokens: TokenResponse) {
        try? keychain.set(tokens.accessToken, for: accessKey)
        try? keychain.set(tokens.refreshToken, for: refreshKey)
        accessToken = tokens.accessToken
    }
}
