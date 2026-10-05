import SwiftUI

/// Poll the exact server task, rather than guessing from the latest agent message.
struct TaskResponseView: View {
    let taskId: String
    @EnvironmentObject private var viewModel: MonitorViewModel
    @Environment(\.dismiss) private var dismiss
    @State private var errorMessage: String?

    private var task: AgentTask? { viewModel.tasks.first { $0.id == taskId } }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    Text(task?.title ?? "Task response").font(.title2)
                    Text("Task ID: \(taskId)")
                        .font(.caption).textSelection(.enabled)
                        .accessibilityIdentifier("task.response.id")
                    if let task {
                        Text("Status: \(task.status.rawValue)")
                            .accessibilityIdentifier("task.response.status")
                        if let result = task.result, !result.isEmpty {
                            Text(result).textSelection(.enabled)
                                .accessibilityIdentifier("task.response.body")
                        } else {
                            Text("Waiting for the agent's response…")
                        }
                    }
                    if let errorMessage {
                        Text(errorMessage).foregroundColor(.red)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding()
            }
            .navigationTitle("Agent Response")
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                }
                ToolbarItem(placement: .automatic) {
                    Button("Refresh") { Task { await refresh() } }
                }
            }
            .task(id: taskId) {
                while !Task.isCancelled {
                    await refresh()
                    if let status = task?.status, [.completed, .failed, .cancelled].contains(status) { break }
                    do { try await Task.sleep(nanoseconds: 2_000_000_000) }
                    catch { break }
                }
            }
        }
    }

    private func refresh() async {
        do {
            try await viewModel.refreshTask(taskId: taskId)
            errorMessage = nil
        } catch { errorMessage = error.localizedDescription }
    }
}