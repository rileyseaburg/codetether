import Foundation

/// A worker-advertised model with an explicit, provider-qualified routing ID.
struct WorkerModelOption: Codable, Hashable, Identifiable {
    let id: String
    let name: String
    let provider: String
    let available: Bool

    init(id: String, name: String? = nil, provider: String? = nil, available: Bool = true) {
        let trimmed = id.trimmingCharacters(in: .whitespacesAndNewlines)
        let qualified = provider.map { trimmed.hasPrefix($0 + "/") ? trimmed : $0 + "/" + trimmed } ?? trimmed
        self.id = qualified
        self.provider = provider ?? qualified.split(separator: "/", maxSplits: 1).first.map(String.init) ?? "Unknown"
        self.name = name ?? qualified.split(separator: "/", maxSplits: 1).last.map(String.init) ?? qualified
        self.available = available && qualified.contains("/") && !qualified.hasSuffix("/")
    }

    private enum Keys: String, CodingKey { case id, name, provider, available, providerId = "provider_id" }
    init(from decoder: Decoder) throws {
        if let id = try? decoder.singleValueContainer().decode(String.self) {
            self.init(id: id)
            return
        }
        let values = try decoder.container(keyedBy: Keys.self)
        let provider = try values.decodeIfPresent(String.self, forKey: .providerId)
            ?? values.decodeIfPresent(String.self, forKey: .provider)
        self.init(id: try values.decode(String.self, forKey: .id),
            name: try values.decodeIfPresent(String.self, forKey: .name), provider: provider,
            available: try values.decodeIfPresent(Bool.self, forKey: .available) ?? true)
    }

    var providerName: String {
        switch provider {
        case "github-copilot": return "GitHub Copilot"
        case "openai-codex": return "OpenAI Codex"
        case "openrouter": return "OpenRouter"
        case "zai": return "Z.ai"
        case "google": return "Google"
        case "bedrock": return "Amazon Bedrock"
        default: return provider
        }
    }

    static func choices(_ options: [WorkerModelOption]) -> [WorkerModelOption] {
        var seen = Set<String>()
        return options.filter { $0.available && seen.insert($0.id).inserted }.sorted {
            if $0.provider != $1.provider { return $0.provider.localizedStandardCompare($1.provider) == .orderedAscending }
            return $0.name.localizedStandardCompare($1.name) == .orderedAscending
        }
    }

    static func preferredID(in models: [WorkerModelOption]) -> String? {
        let choices = choices(models)
        for preferred in ["github-copilot/gpt-5-mini", "github-copilot/gpt-5.3-codex", "zai/glm-5"] {
            if choices.contains(where: { $0.id == preferred }) { return preferred }
        }
        return choices.first?.id
    }
}