import XCTest
@testable import A2AMonitor

final class AgentTaskTests: XCTestCase {
    func testTaskResponsePreservesServerIdentity() throws {
        let data = Data(#"{"id":"server-task-123","title":"HTML proof","prompt":"Create the page","workspace_id":"workspace-1","priority":0,"status":"running"}"#.utf8)
        let task = try JSONDecoder().decode(AgentTask.self, from: data)
        XCTAssertEqual(task.id, "server-task-123")
        XCTAssertEqual(task.description, "Create the page")
        XCTAssertEqual(task.codebaseId, "workspace-1")
        XCTAssertEqual(task.priority, .normal)
        XCTAssertEqual(task.status, .working)
        let legacy = Data(#"{"id":"legacy-task","description":"Legacy prompt","codebase_id":"legacy-workspace"}"#.utf8)
        let oldTask = try JSONDecoder().decode(AgentTask.self, from: legacy)
        XCTAssertEqual(oldTask.codebaseId, "legacy-workspace")
        XCTAssertEqual(oldTask.description, "Legacy prompt")
        let error = Data(#"{"detail":"Not authenticated"}"#.utf8)
        XCTAssertThrowsError(try JSONDecoder().decode(AgentTask.self, from: error))
    }
}
