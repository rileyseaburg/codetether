import XCTest
@testable import A2AMonitor

final class WorkerModelOptionTests: XCTestCase {
    func testLegacyAndRichModelsPreserveProviderQualifiedIds() throws {
        let json = #"["github-copilot/gpt-5-mini",{"id":"openrouter/openai/gpt-5-mini","name":"GPT-5 Mini","provider_id":"openrouter"},{"id":"glm-5","provider_id":"zai"}]"#
        let models = try JSONDecoder().decode([WorkerModelOption].self, from: Data(json.utf8))
        XCTAssertEqual(models.map(\.id), ["github-copilot/gpt-5-mini", "openrouter/openai/gpt-5-mini", "zai/glm-5"])
        XCTAssertEqual(models[0].providerName, "GitHub Copilot")
        XCTAssertEqual(models[1].name, "GPT-5 Mini")
    }

    func testPickerOmitsUnavailableAndAmbiguousModels() {
        let models = [WorkerModelOption(id: "unqualified"),
            WorkerModelOption(id: "provider/"), WorkerModelOption(id: "provider/disabled", available: false),
            WorkerModelOption(id: "github-copilot/gpt-5-mini"), WorkerModelOption(id: "github-copilot/gpt-5-mini")]
        XCTAssertEqual(WorkerModelOption.choices(models).map(\.id), ["github-copilot/gpt-5-mini"])
        XCTAssertEqual(WorkerModelOption.preferredID(in: models), "github-copilot/gpt-5-mini")
        XCTAssertNil(WorkerModelOption.preferredID(in: []))
    }

    func testBackendDisabledIsNotDescribedAsModelUnavailable() {
        let failure = AgentCallFailure("Error: OpenAI Codex ChatGPT backend is disabled. Configure OPENAI_API_KEY.")
        XCTAssertEqual(failure.title, "Selected backend is disabled")
        XCTAssertTrue(failure.canChooseModel)
        XCTAssertTrue(failure.message.contains("conversation is retained"))
        XCTAssertFalse(failure.message.contains("model is unavailable"))
    }

    func testGitFailureDoesNotRecommendChangingProvider() {
        let failure = AgentCallFailure("Post-agent git commit/push failed: non-fast-forward")
        XCTAssertFalse(failure.canChooseModel)
        XCTAssertTrue(failure.message.contains("do not force-push"))
    }
}