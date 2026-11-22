import XCTest
import SwiftUI
#if os(iOS)
import UIKit
#endif
@testable import A2AMonitor

final class WorkSessionTests: XCTestCase {
    @MainActor
    func testChangeModelAndRetryPreservesFailedTurnAndConversation() async throws {
        let model = controller()
        await model.refresh()
        let worker = try XCTUnwrap(model.onlineWorkers.first)
        let project = try XCTUnwrap(model.projects(for: worker).first)
        let id = try await model.start(worker: worker, workspace: project, prompt: "Fail once", model: "openai-codex/gpt-6-astra")
        try await model.poll(id)
        XCTAssertEqual(model.session(id)?.turns.last?.status, .failed)
        XCTAssertEqual(model.session(id)?.currentTaskId, "task-disabled")
        try model.selectModel("github-copilot/gpt-5-mini", for: id)
        try await model.retry(id)
        try await model.poll(id)
        XCTAssertEqual(model.session(id)?.turns.count, 2)
        XCTAssertEqual(model.session(id)?.turns.first?.taskId, "task-disabled")
        XCTAssertEqual(model.session(id)?.turns.last?.taskId, "task-recovered")
        XCTAssertEqual(model.session(id)?.turns.last?.response, "Recovered")
        XCTAssertEqual(model.session(id)?.remoteSessionId, "remote-1")
        XCTAssertEqual(model.session(id)?.model, "github-copilot/gpt-5-mini")
        XCTAssertThrowsError(try model.selectModel("made-up/model", for: id))
    }

    func testWorkerSessionIdFromTaskMetadata() throws {
        let data = Data(#"{"id":"task","metadata":{"session_id":"central","worker_session_id":"worker-session"}}"#.utf8)
        let task = try JSONDecoder().decode(AgentTask.self, from: data)
        XCTAssertEqual(task.sessionId, "worker-session")
        let ordinary = Data(#"{"id":"task","metadata":{"session_id":"worker-session"}}"#.utf8)
        XCTAssertEqual(try JSONDecoder().decode(AgentTask.self, from: ordinary).sessionId, "worker-session")
    }
    #if os(iOS)
    @MainActor
    func testRenderedAgentAndChatScreens() async throws {
        let model = controller()
        await model.refresh()
        let auth = AuthService()
        let monitor = MonitorViewModel()
        try await snapshot(NavigationStack {
            AgentWorkspaceView(controller: model).environmentObject(auth).environmentObject(monitor)
        }, named: "agents-home-mocked")
        let worker = try XCTUnwrap(model.onlineWorkers.first)
        let workspace = try XCTUnwrap(model.projects(for: worker).first)
        try await snapshot(NewWorkSessionView(controller: model, preferredWorkerId: worker.workerId, onStarted: { _ in }),
            named: "new-work-session-mocked")
        let id = try await model.start(worker: worker, workspace: workspace, prompt: "First message", model: "github-copilot/gpt-5-mini")
        try await model.poll(id)
        try await model.send("Follow up", to: id)
        try await model.poll(id)
        try await snapshot(NavigationStack { WorkChatView(controller: model, sessionId: id) }, named: "work-chat-mocked")
    }

    @MainActor
    private func snapshot<Content: View>(_ content: Content, named name: String) async throws {
        let scene = try XCTUnwrap(UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }
            .first { $0.activationState == .foregroundActive })
        let previous = scene.windows.first { $0.isKeyWindow }
        let window = UIWindow(windowScene: scene)
        window.frame = UIScreen.main.bounds
        window.rootViewController = UIHostingController(rootView: content.preferredColorScheme(.dark))
        window.makeKeyAndVisible()
        defer { window.isHidden = true; previous?.makeKeyAndVisible() }
        var renderedImage: UIImage?
        // Wait for SwiftUI display transactions; never accept a blank fallback.
        for _ in 0..<12 {
            try await Task.sleep(nanoseconds: 250_000_000)
            window.layoutIfNeeded()
            var rendered = false
            let image = UIGraphicsImageRenderer(bounds: window.bounds).image { _ in
                rendered = window.drawHierarchy(in: window.bounds, afterScreenUpdates: true)
            }
            if rendered { renderedImage = image; break }
        }
        let image = try XCTUnwrap(renderedImage, "SwiftUI hierarchy did not render for \(name)")
        let attachment = XCTAttachment(image: image)
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }
    #endif

    @MainActor
    private func controller(host: String = "work.test") -> WorkSessionController {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [WorkProtocol.self]
        return WorkSessionController(client: A2AClient(baseURL: "https://\(host)", session: URLSession(configuration: configuration)))
    }

    @MainActor
    func testDiscoverStartReplyAndContinueSameWorkerSession() async throws {
        let controller = controller()
        await controller.refresh()
        XCTAssertNil(controller.errorMessage)
        XCTAssertEqual(controller.onlineWorkers.count, 1)
        let worker = try XCTUnwrap(controller.onlineWorkers.first)
        XCTAssertFalse(worker.isHarvester, "A persistent local worker is not automatically a Kubernetes harvester")
        let workspace = try XCTUnwrap(controller.projects(for: worker).first)
        let id = try await controller.start(worker: worker, workspace: workspace, prompt: "First message", model: "github-copilot/gpt-5-mini")
        XCTAssertEqual(controller.session(id)?.currentTaskId, "task-first")
        XCTAssertTrue(controller.session(id)?.isRunning == true)
        do { try await controller.send("duplicate", to: id); XCTFail("Concurrent turn must be rejected") }
        catch WorkSessionError.alreadyRunning { }
        try await controller.poll(id)
        XCTAssertEqual(controller.session(id)?.remoteSessionId, "remote-1")
        XCTAssertEqual(controller.session(id)?.turns.last?.response, "First reply")
        try await controller.send("Follow up", to: id)
        XCTAssertEqual(controller.session(id)?.currentTaskId, "task-second")
        try await controller.poll(id)
        XCTAssertEqual(controller.session(id)?.turns.count, 2)
        XCTAssertEqual(controller.session(id)?.remoteSessionId, "remote-1")
        XCTAssertEqual(controller.session(id)?.turns.last?.response, "Second reply")
    }

    @MainActor
    func testUnauthorizedDiscoveryShowsErrorInsteadOfEmptyFleet() async {
        let controller = controller(host: "unauthorized.test")
        await controller.refresh()
        XCTAssertNotNil(controller.errorMessage)
        XCTAssertFalse(controller.isRefreshing)
    }

    @MainActor
    func testMissingServerSessionIdUsesStableA2AContext() async throws {
        let controller = controller()
        await controller.refresh()
        let worker = try XCTUnwrap(controller.onlineWorkers.first)
        let workspace = try XCTUnwrap(controller.projects(for: worker).first)
        let id = try await controller.start(worker: worker, workspace: workspace, prompt: "No session", model: nil)
        try await controller.poll(id)
        XCTAssertTrue(controller.session(id)?.contextId.hasPrefix("ios-") == true)
        try await controller.send("Follow up", to: id)
        XCTAssertEqual(controller.session(id)?.currentTaskId, "task-second")
    }
}

private final class WorkProtocol: URLProtocol {
    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
    override func stopLoading() {}
    override func startLoading() {
        var code = 200
        var body = "{}"
        let url = request.url!
        if url.host == "unauthorized.test" { code = 401 }
        else if url.path == "/v1/agent/workers" {
            body = #"[{"worker_id":"worker-1","name":"local","status":"active","capabilities":["persistent-workspace","session-context"],"workspaces":["/repo"],"models":["github-copilot/gpt-5-mini","openai-codex/gpt-6-astra"]},{"worker_id":"stale","name":"old","status":"offline"}]"#
        } else if url.path == "/v1/agent/workspaces" {
            body = #"[{"id":"workspace-1","name":"Project","path":"/repo","worker_id":"worker-1"}]"#
        } else if request.httpMethod == "POST" && url.path == "/v1/agent/workspaces/workspace-1/tasks" {
            let payload = jsonBody()
            let metadata = payload["metadata"] as? [String: String] ?? [:]
            if payload["model"] == nil || metadata["target_worker_id"] != "worker-1" || metadata["target_agent_name"] != "local" || metadata["context_id"]?.hasPrefix("ios-") != true {
                code = 422
            } else if payload["prompt"] as? String == "Fail once" {
                let first = payload["model"] as? String == "openai-codex/gpt-6-astra"
                if !first && metadata["resume_session_id"] != "remote-1" { code = 422 }
                body = first ? #"{"task":{"id":"task-disabled","status":"pending"}}"#
                    : #"{"task":{"id":"task-recovered","status":"pending"}}"#
            } else if payload["prompt"] as? String == "Follow up" {
                if metadata["resume_session_id"] != "remote-1" && metadata["resume_session_id"] != metadata["context_id"] { code = 422 }
                else { body = #"{"task":{"id":"task-second","status":"pending"}}"# }
            } else if payload["prompt"] as? String == "No session" {
                body = #"{"task":{"id":"task-no-session","status":"pending"}}"#
            } else { body = #"{"task":{"id":"task-first","status":"pending"}}"# }
        } else if url.path == "/v1/agent/tasks/task-disabled" {
            body = #"{"id":"task-disabled","status":"completed","session_id":"remote-1","error":"OpenAI Codex ChatGPT backend is disabled"}"#
        } else if url.path == "/v1/agent/tasks/task-recovered" {
            body = #"{"id":"task-recovered","status":"completed","session_id":"remote-1","result":"Recovered"}"#
        } else if url.path == "/v1/agent/tasks/task-first" {
            body = #"{"id":"task-first","status":"completed","session_id":"remote-1","result":"First reply"}"#
        } else if url.path == "/v1/agent/tasks/task-second" {
            body = #"{"id":"task-second","status":"completed","session_id":"remote-1","result":"Second reply"}"#
        } else if url.path == "/v1/agent/tasks/task-no-session" {
            body = #"{"id":"task-no-session","status":"completed","result":"No conversation ID"}"#
        } else { code = 404 }
        let response = HTTPURLResponse(url: url, statusCode: code, httpVersion: nil, headerFields: ["Content-Type": "application/json"])!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: Data(body.utf8))
        client?.urlProtocolDidFinishLoading(self)
    }
    private func jsonBody() -> [String: Any] {
        var data = request.httpBody ?? Data()
        if data.isEmpty, let stream = request.httpBodyStream {
            stream.open(); defer { stream.close() }
            var buffer = [UInt8](repeating: 0, count: 1024)
            while stream.hasBytesAvailable {
                let count = stream.read(&buffer, maxLength: buffer.count)
                if count <= 0 { break }
                data.append(contentsOf: buffer.prefix(count))
            }
        }
        return (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] ?? [:]
    }
}