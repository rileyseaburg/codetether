import XCTest
@testable import A2AMonitor

/// Opt-in LIVE integration test; no URLProtocol fixtures or user credentials.
final class LiveSimulatorTaskTests: XCTestCase {
    private struct Configuration: Decodable {
        let marker: String
        let workerId: String
        let workspaceId: String
        let title: String
        let prompt: String
        let model: String
        let url: String
    }

    @MainActor
    func testRealSimulatorTaskRoundTrip() async throws {
        guard ProcessInfo.processInfo.environment["A2A_LIVE_SIMULATOR_TEST"] == "1" else {
            throw XCTSkip("Opt-in live simulator integration is disabled")
        }
        let base = URL(string: "http://127.0.0.1:18770")!
        let (configData, response) = try await URLSession.shared.data(from: base.appendingPathComponent("test-config"))
        XCTAssertEqual((response as? HTTPURLResponse)?.statusCode, 200)
        let config = try JSONDecoder().decode(Configuration.self, from: configData)
        let model = MonitorViewModel(client: A2AClient(baseURL: base.absoluteString))
        let workspace = Codebase(id: config.workspaceId, name: "Live simulator proof", path: "/live-test",
            workerId: config.workerId)
        model.codebases = [workspace]
        try await model.createTask(codebase: workspace, title: config.title, description: config.prompt,
            priority: .normal, context: nil, model: config.model)
        let taskId = try XCTUnwrap(model.lastSubmittedTaskId)
        XCTAssertFalse(taskId.isEmpty)
        let deadline = Date().addingTimeInterval(600)
        while Date() < deadline {
            try await model.refreshTask(taskId: taskId)
            let task = try XCTUnwrap(model.tasks.first(where: { $0.id == taskId }))
            if task.status == .completed { break }
            if task.status == .failed || task.status == .cancelled {
                XCTFail("Live worker task ended unsuccessfully: \(taskId)")
                return
            }
            try await Task.sleep(nanoseconds: 3_000_000_000)
        }
        let task = try XCTUnwrap(model.tasks.first(where: { $0.id == taskId }))
        XCTAssertEqual(task.status, .completed, "Live task timed out: \(taskId)")
        XCTAssertTrue(task.result?.contains(config.url) == true)
        let (proof, checked) = try await URLSession.shared.data(from: base.appendingPathComponent("verify"))
        XCTAssertEqual((checked as? HTTPURLResponse)?.statusCode, 200)
        let object = try XCTUnwrap(JSONSerialization.jsonObject(with: proof) as? [String: Any])
        XCTAssertEqual(object["taskId"] as? String, taskId)
        XCTAssertEqual(object["httpStatus"] as? Int, 200)
        let attachment = XCTAttachment(data: proof, uniformTypeIdentifier: "public.json")
        attachment.name = "live-simulator-task-proof"
        attachment.lifetime = .keepAlways
        add(attachment)
    }
}