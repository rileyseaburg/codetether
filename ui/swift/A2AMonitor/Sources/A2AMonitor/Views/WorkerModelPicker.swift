import SwiftUI

struct WorkerModelPicker: View {
    let models: [WorkerModelOption]
    @Binding var selection: String
    @Environment(\.dismiss) private var dismiss
    @State private var search = ""

    private var filtered: [WorkerModelOption] {
        let query = search.trimmingCharacters(in: .whitespacesAndNewlines)
        return models.filter { query.isEmpty || "\($0.name) \($0.providerName) \($0.id)".localizedCaseInsensitiveContains(query) }
    }
    private var recommended: [WorkerModelOption] {
        let preferred = WorkerModelOption.preferredID(in: models)
        return filtered.filter { $0.id == preferred }
    }

    var body: some View {
        let recommendedIDs = Set(recommended.map(\.id))
        let groups = Dictionary(grouping: filtered.filter { !recommendedIDs.contains($0.id) }, by: \.provider)
        NavigationStack {
            List {
                Section {
                    Text("Choose a model advertised by this agent. The selected provider and model are sent together.")
                        .font(.caption).foregroundStyle(.secondary)
                }
                if !recommended.isEmpty {
                    Section("Recommended") { ForEach(recommended) { option($0) } }
                }
                ForEach(groups.keys.sorted(), id: \.self) { provider in
                    let choices = groups[provider] ?? []
                    if let first = choices.first {
                        Section(first.providerName) { ForEach(choices) { option($0) } }
                    }
                }
                if filtered.isEmpty {
                    Text(models.isEmpty ? "This agent has not advertised any models. Refresh the agent list." : "No matching models.")
                        .foregroundStyle(.secondary)
                }
            }
            .navigationTitle("Choose Model")
            .searchable(text: $search, prompt: "Search models or providers")
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } } }
        }
    }

    private func option(_ model: WorkerModelOption) -> some View {
        Button {
            selection = model.id
            dismiss()
        } label: {
            HStack {
                VStack(alignment: .leading) {
                    Text(model.name).foregroundStyle(.primary)
                    Text(model.providerName).font(.caption).foregroundStyle(.secondary)
                }
                Spacer()
                if selection == model.id { Image(systemName: "checkmark.circle.fill").foregroundStyle(.cyan) }
            }
        }.accessibilityIdentifier("model.option.\(model.id)")
    }
}