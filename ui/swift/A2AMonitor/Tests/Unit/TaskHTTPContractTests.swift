import XCTest
@testable import A2AMonitor

/// Exercises the real client methods with local HTTP fixtures, not a backend.
final class TaskHTTPContractTests: XCTestCase {
    @MainActor
    func testTasksScreenSubmissionRoutesAndReturnsSameTask() async throws {
        let model = MonitorViewModel(client: client())
        let workspace = Codebase(id: "workspace-local", name: "Local test", path: "/fixture",
            workerId: "worker-local")
        model.codebases = [workspace]
        try await model.createTask(codebase: workspace, title: "HTML proof",
            description: "Create the page", priority: .normal, context: "ios-e2e",
            model: "github-copilot/gpt-5-mini")
        XCTAssertEqual(model.lastSubmittedTaskId, "local-task-456")
        XCTAssertEqual(model.tasks.first?.id, "local-task-456")
        try await model.refreshTask(taskId: "local-task-456")
        XCTAssertEqual(model.tasks.count, 1)
        XCTAssertEqual(model.tasks.first?.status, .completed)
        XCTAssertEqual(model.tasks.first?.result, "https://example.invalid/local.html")
        XCTAssertEqual(model.tasks.first?.id, model.lastSubmittedTaskId)
    }

    @MainActor
    private func client() -> A2AClient {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [TaskFixtureProtocol.self]
        return A2AClient(baseURL: "https://ios-contract.invalid", session: URLSession(configuration: configuration))
    }

    @MainActor
    func testCreateTaskDecodesSuccessEnvelope() async throws {
        let task = try await client().createTask(codebaseId: "workspace-1", title: "HTML proof",
            description: "Create the page", priority: .normal, context: nil)
        XCTAssertEqual(task.id, "server-task-123")
        XCTAssertEqual(task.codebaseId, "workspace-1")
        XCTAssertEqual(task.description, "Create the page")
    }

    @MainActor
    func testFetchTaskDecodesBareObject() async throws {
        let task = try await client().fetchTask(taskId: "server-task-123")
        XCTAssertEqual(task.id, "server-task-123")
        XCTAssertEqual(task.result, "https://example.invalid/proof.html")
    }

    @MainActor
    func testCreateRejectsHTTPFailure() async {
        do {
            _ = try await client().createTask(codebaseId: "denied", title: "HTML proof",
                description: "Create the page", priority: .normal, context: nil)
            XCTFail("A denied creation must not manufacture a task")
        } catch A2AError.httpFailure(let status) {
            XCTAssertEqual(status, 403)
        } catch { XCTFail("Unexpected error: \(error)") }
    }

    @MainActor
    func testFetchRejectsHTTPFailure() async {
        do {
            _ = try await client().fetchTask(taskId: "denied")
            XCTFail("A denied fetch must not manufacture a task")
        } catch A2AError.httpFailure(let status) {
            XCTAssertEqual(status, 403)
        } catch { XCTFail("Unexpected error: \(error)") }
    }
}

private final class TaskFixtureProtocol: URLProtocol {
    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
    override func startLoading() {
        let task = #"{"id":"server-task-123","title":"HTML proof","prompt":"Create the page","workspace_id":"workspace-1","priority":0,"result":"https://example.invalid/proof.html"}"#
        let status: Int
        let body: String
        if request.url!.path.contains("denied") {
            status = 403; body = #"{"detail":"Forbidden"}"#
        } else if request.httpMethod == "POST" && request.url!.path == "/v1/agent/workspaces/workspace-local/tasks" {
            let payload = requestPayload()
            let metadata = payload["metadata"] as? [String: String]
            if metadata?["target_worker_id"] == "worker-local" && metadata?["context"] == "ios-e2e"
                && payload["model"] as? String == "github-copilot/gpt-5-mini"
                && payload["prompt"] as? String == "Create the page" {
                status = 200
                body = #"{"success":true,"task":{"id":"local-task-456","workspace_id":"workspace-local","status":"pending"}}"#
            } else {
                status = 422; body = #"{"detail":"Missing explicit local-worker routing"}"#
            }
        } else if request.httpMethod == "GET" && request.url!.path == "/v1/agent/tasks/local-task-456" {
            status = 200; body = #"{"id":"local-task-456","workspace_id":"workspace-local","status":"completed","result":"https://example.invalid/local.html"}"#
        } else if request.httpMethod == "POST" && request.url!.path == "/v1/agent/workspaces/workspace-1/tasks" {
            status = 201; body = "{\"success\":true,\"task\":\(task)}"
        } else if request.httpMethod == "GET" && request.url!.path == "/v1/agent/tasks/server-task-123" {
            status = 200; body = task
        } else {
            status = 404; body = #"{"detail":"Unexpected test route"}"#
        }
        let response = HTTPURLResponse(url: request.url!, statusCode: status,
            httpVersion: nil, headerFields: ["Content-Type": "application/json"])!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: Data(body.utf8))
        client?.urlProtocolDidFinishLoading(self)
    }
    override func stopLoading() {}

    private func requestPayload() -> [String: Any] {
        var data = request.httpBody ?? Data()
        if data.isEmpty, let stream = request.httpBodyStream {
            stream.open()
            defer { stream.close() }
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