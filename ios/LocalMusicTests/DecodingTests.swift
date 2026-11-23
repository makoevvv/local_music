import XCTest
@testable import LocalMusic

final class DecodingTests: XCTestCase {
    func testTokenAndTrackListUseSnakeCase() throws {
        let tokens = try JSONDecoder.api.decode(
            TokenResponse.self,
            from: Data("""
            {"access_token":"a","refresh_token":"r","expires_in":3600,"token_type":"bearer"}
            """.utf8)
        )
        XCTAssertEqual(tokens.accessToken, "a")
        XCTAssertEqual(tokens.refreshToken, "r")

        let page = try JSONDecoder.api.decode(
            TrackListResponse.self,
            from: Data("""
            {"items":[{"id":"t1","title":"Numb","duration_seconds":187,"status":"ready","play_count":3,"has_lyrics":true,"artists":[{"id":"a1","name":"Linkin Park"}],"album":{"id":"al1","title":"Meteora","release_year":2003},"unverified":false,"user_sentiment":null}],"page":1,"page_size":20,"total":1}
            """.utf8)
        )
        XCTAssertEqual(page.items[0].title, "Numb")
        XCTAssertEqual(page.items[0].artistLine, "Linkin Park")
        XCTAssertEqual(page.items[0].album?.releaseYear, 2003)
        XCTAssertEqual(page.total, 1)
    }

    func testPlaylistListDecodes() throws {
        let playlists = try JSONDecoder.api.decode(
            [PlaylistSummary].self,
            from: Data("""
            [{"id":"p1","name":"Любимое","is_favourite":true,"is_public":false,"track_count":2,"created_at":"2026-11-24T00:00:00Z"}]
            """.utf8)
        )
        XCTAssertEqual(playlists[0].name, "Любимое")
        XCTAssertTrue(playlists[0].isFavourite)
        XCTAssertEqual(playlists[0].trackCount, 2)
    }
}
