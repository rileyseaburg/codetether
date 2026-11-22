import XCTest
@testable import A2AMonitor

final class ProjectDiscoveryTests: XCTestCase {
    private func worker(paths: [String]) throws -> AgentWorker {
        let data = try JSONSerialization.data(withJSONObject: [
            "worker_id": "harvester", "status": "active", "workspaces": paths,
            "capabilities": ["session-context"]
        ])
        return try JSONDecoder().decode(AgentWorker.self, from: data)
    }

    @MainActor
    func testSharedCloneRootDoesNotClaim1939HistoricalWorkspaces() throws {
        let root = "/var/lib/codetether/repos"
        let worker = try worker(paths: [root])
        var projects = [Codebase(id: "owned", name: "Current project", path: root + "/owned", workerId: "harvester")]
        projects += (0..<631).map {
            Codebase(id: "foreign-\($0)", name: "Old checkout", path: root + "/foreign-\($0)", workerId: "old-worker")
        }
        projects += (0..<1307).map {
            Codebase(id: "unassigned-\($0)", name: "Unassigned checkout", path: root + "/unassigned-\($0)")
        }
        XCTAssertEqual(projects.count, 1939)
        XCTAssertEqual(WorkSessionController.selectableProjects(projects, for: worker).map(\.id), ["owned"])
    }

    @MainActor
    func testExactAdvertisementOnlyFillsMissingOwnership() throws {
        let worker = try worker(paths: ["/repos", "/repos/exact/", "/repos/foreign", ""])
        let projects = [
            Codebase(id: "owned", name: "A", path: "/another-volume/project", workerId: "harvester"),
            Codebase(id: "exact", name: "B", path: "/repos/exact"),
            Codebase(id: "descendant", name: "C", path: "/repos/exact/old-checkout"),
            Codebase(id: "foreign", name: "D", path: "/repos/foreign", workerId: "other-worker"),
            Codebase(id: "sibling", name: "E", path: "/repos/exact-sibling"),
            Codebase(id: "empty", name: "F", path: "")
        ]
        XCTAssertEqual(WorkSessionController.selectableProjects(projects, for: worker).map(\.id), ["owned", "exact"])
    }

    @MainActor
    func testRootAdvertisementDoesNotClaimEveryAbsolutePath() throws {
        let worker = try worker(paths: ["/"])
        let projects = [Codebase(id: "other", name: "Unrelated", path: "/somewhere/else")]
        XCTAssertTrue(WorkSessionController.selectableProjects(projects, for: worker).isEmpty)
    }

    @MainActor
    func testEmptyOwnerAndTrailingSeparatorUseExactFolderFallback() throws {
        let worker = try worker(paths: ["/repos/exact"])
        let projects = [Codebase(id: "exact", name: "Exact", path: "/repos/exact/", workerId: "")]
        XCTAssertEqual(WorkSessionController.selectableProjects(projects, for: worker).map(\.id), ["exact"])
    }
}