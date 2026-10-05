import XCTest
import SwiftUI
@testable import A2AMonitor

final class LiveWorkSessionTests: XCTestCase {
    private struct Configuration: Decodable {
        struct Target: Decodable { let workerId: String; let workspaceId: String; let firstPrompt: String; let marker: String }
        let targets: [Target]
        let secondPrompt: String
    }
    @MainActor
    func testLiveLocalAndHarvesterConversations() async throws {
        guard ProcessInfo.processInfo.environment["A2A_LIVE_SIMULATOR_TEST"] == "1" else { throw XCTSkip("Live test is opt-in") }
        let base = URL(string: "http://127.0.0.1:19872")!
        let (data, response) = try await URLSession.shared.data(from: base.appendingPathComponent("test-config"))
        XCTAssertEqual((response as? HTTPURLResponse)?.statusCode, 200)
        let config = try JSONDecoder().decode(Configuration.self, from: data)
        let controller = WorkSessionController(client: A2AClient(baseURL: base.absoluteString))
        await controller.refresh()
        XCTAssertNil(controller.errorMessage)
        var lastSession: UUID?
        for target in config.targets {
            let worker = try XCTUnwrap(controller.onlineWorkers.first { $0.workerId == target.workerId })
            let project = try XCTUnwrap(controller.projects(for: worker).first { $0.id == target.workspaceId })
            let id = try await controller.start(worker: worker, workspace: project,
                prompt: target.firstPrompt, model: "github-copilot/gpt-5-mini")
            try await waitForTurn(controller, id)
            let firstTask = controller.session(id)?.currentTaskId
            try await controller.send(config.secondPrompt, to: id)
            XCTAssertNotEqual(controller.session(id)?.currentTaskId, firstTask)
            try await waitForTurn(controller, id)
            XCTAssertTrue(controller.session(id)?.turns.last?.response?.contains(target.marker) == true,
                "Worker did not remember the previous turn")
            lastSession = id
        }
        let (proof, checked) = try await URLSession.shared.data(from: base.appendingPathComponent("verify"))
        XCTAssertEqual((checked as? HTTPURLResponse)?.statusCode, 200)
        let attachment = XCTAttachment(data: proof, uniformTypeIdentifier: "public.json")
        attachment.name = "live-work-session-proof"
        attachment.lifetime = .keepAlways
        add(attachment)
        #if os(iOS)
        if let lastSession {
            let renderer = ImageRenderer(content: NavigationStack {
                WorkChatView(controller: controller, sessionId: lastSession)
            }.preferredColorScheme(.dark).frame(width: 402, height: 874))
            renderer.scale = 2
            if let image = renderer.uiImage {
                let screenshot = XCTAttachment(image: image)
                screenshot.name = "live-work-conversation"
                screenshot.lifetime = .keepAlways
                add(screenshot)
            }
        }
        #endif
    }

    @MainActor
    private func waitForTurn(_ controller: WorkSessionController, _ id: UUID) async throws {
        let deadline = Date().addingTimeInterval(480)
        while Date() < deadline {
            try await controller.poll(id)
            guard let turn = controller.session(id)?.turns.last else { throw WorkSessionError.missingSession }
            if turn.status == .completed { return }
            if [.failed, .cancelled].contains(turn.status) {
                XCTFail("Task failed: \(turn.taskId ?? "missing") / \(turn.error ?? "unknown")")
                throw WorkSessionError.wrongTask
            }
            try await Task.sleep(nanoseconds: 3_000_000_000)
        }
        XCTFail("Timed out waiting for live agent response")
        throw WorkSessionError.wrongTask
    }
}


