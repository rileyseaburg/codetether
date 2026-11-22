import XCTest

/// Opt-in, real button-to-worker test through an isolated service-auth bridge.
/// Uses the app's existing Guest entry, not user credentials or a login bypass.
final class WorkSessionUITests: XCTestCase {
    private struct Configuration: Decodable {
        struct Target: Decodable { let workerId: String; let firstPrompt: String; let marker: String }
        let targets: [Target]
        let secondPrompt: String
    }
    @MainActor
    func testDiscoverStartAndMessageThroughUI() async throws {
        continueAfterFailure = false
        guard ProcessInfo.processInfo.environment["A2A_LIVE_SIMULATOR_TEST"] == "1" else { throw XCTSkip("Live UI test is opt-in") }
        let base = URL(string: "http://127.0.0.1:19872")!
        let (data, _) = try await URLSession.shared.data(from: base.appendingPathComponent("test-config"))
        let config = try JSONDecoder().decode(Configuration.self, from: data)
        let target = try XCTUnwrap(config.targets.first)
        print("WORKFLOW_STAGE config-loaded")
        let app = XCUIApplication()
        app.launchArguments = ["-hasSeenOnboarding", "YES", "-serverURL", base.absoluteString]
        app.launch()
        print("WORKFLOW_STAGE app-launched")
        let guest = app.buttons["Continue as Guest"]
        if guest.waitForExistence(timeout: 10) { guest.tap() }
        print("WORKFLOW_STAGE guest-opened")
        let newSession = app.buttons["agents.newSession"]
        XCTAssertTrue(newSession.waitForExistence(timeout: 30))
        let worker = app.descendants(matching: .any).matching(identifier: "agents.worker.\(target.workerId)").firstMatch
        if !worker.waitForExistence(timeout: 45) {
            print("WORKFLOW_STAGE missing-worker-tree \(app.debugDescription)")
            XCTFail("Online worker row was not available")
            return
        }
        screenshot(app, "live-agents-directory")
        print("WORKFLOW_STAGE worker-visible")
        worker.tap()
        let prompt = app.textViews["workSession.prompt"]
        XCTAssertTrue(prompt.waitForExistence(timeout: 10))
        print("WORKFLOW_STAGE form-opened")
        let model = app.buttons["workSession.model"]
        XCTAssertTrue(model.exists, "Model must be a picker, not a free-text field")
        XCTAssertFalse(app.textFields["workSession.model"].exists)
        model.tap()
        let choice = app.buttons["model.option.github-copilot/gpt-5-mini"]
        XCTAssertTrue(choice.waitForExistence(timeout: 10))
        choice.tap()
        print("WORKFLOW_STAGE model-selected")
        prompt.tap()
        prompt.typeText(target.firstPrompt)
        let start = app.buttons["workSession.start"]
        if !start.isHittable { app.swipeUp() }
        guard start.isEnabled else {
            screenshot(app, "disabled-start-session")
            XCTFail("Start Session was disabled after entering a prompt")
            return
        }
        screenshot(app, "live-new-session")
        start.tap()
        print("WORKFLOW_STAGE submitted")
        let composer = app.descendants(matching: .any).matching(identifier: "workChat.message").firstMatch
        guard composer.waitForExistence(timeout: 30) else {
            XCTFail("New session did not open its conversation")
            return
        }
        print("WORKFLOW_STAGE chat-opened")
        let firstReply = app.descendants(matching: .any).matching(identifier: "workChat.response").firstMatch
        XCTAssertTrue(firstReply.waitForExistence(timeout: 300))
        print("WORKFLOW_STAGE first-reply")
        composer.tap()
        composer.typeText(config.secondPrompt)
        let send = app.buttons["workChat.send"]
        XCTAssertTrue(send.isEnabled)
        send.tap()
        let recalled = app.descendants(matching: .any).matching(NSPredicate(format: "identifier == %@ AND label CONTAINS %@", "workChat.response", target.marker)).firstMatch
        XCTAssertTrue(recalled.waitForExistence(timeout: 300), "The agent did not return the remembered code in the chat UI")
        screenshot(app, "live-two-turn-chat")
        let (proof, response) = try await URLSession.shared.data(from: base.appendingPathComponent("verify"))
        XCTAssertEqual((response as? HTTPURLResponse)?.statusCode, 200)
        let attachment = XCTAttachment(data: proof, uniformTypeIdentifier: "public.json")
        attachment.name = "live-ui-task-proof"
        attachment.lifetime = .keepAlways
        add(attachment)
        app.terminate()
    }
    @MainActor
    private func screenshot(_ app: XCUIApplication, _ name: String) {
        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }
}