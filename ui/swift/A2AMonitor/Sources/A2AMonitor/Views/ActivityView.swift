import SwiftUI

/// ActivityView - Combines Messages, Sessions, and Output into a single tabbed view
/// Uses a segmented control to switch between the three sections
struct ActivityView: View {
    @EnvironmentObject var viewModel: MonitorViewModel
    @State private var selectedSegment: ActivitySegment = .messages
    
    enum ActivitySegment: String, CaseIterable {
        case messages = "Messages"
        case sessions = "Sessions"
        case output = "Output"
        
        var icon: String {
            switch self {
            case .messages: return "bubble.left.and.bubble.right"
            case .sessions: return "person.2"
            case .output: return "terminal"
            }
        }
    }
    
    var body: some View {
        VStack(spacing: 0) {
            // Segmented control header
            segmentedControl
                .padding(.horizontal, 16)
                .padding(.top, 12)
                .padding(.bottom, 8)
            
            // Content based on selection
            contentView
        }
        .navigationTitle("Activity")
        #if os(iOS)
        .navigationBarTitleDisplayMode(.large)
        #endif
    }
    
    // MARK: - Segmented Control
    
    private var segmentedControl: some View {
        HStack(spacing: 4) {
            ForEach(ActivitySegment.allCases, id: \.self) { segment in
                segmentButton(for: segment)
            }
        }
        .padding(4)
        .background(Color.white.opacity(0.1))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
    
    private func segmentButton(for segment: ActivitySegment) -> some View {
        Button {
            withAnimation(.easeInOut(duration: 0.2)) {
                selectedSegment = segment
            }
        } label: {
            HStack(spacing: 6) {
                Image(systemName: segment.icon)
                    .font(.system(size: 12, weight: .medium))
                Text(segment.rawValue)
                    .font(.system(size: 13, weight: .medium))
            }
            .foregroundColor(selectedSegment == segment ? .white : .white.opacity(0.6))
            .padding(.horizontal, 12)
            .padding(.vertical, 8)
            .frame(maxWidth: .infinity)
            .background(
                selectedSegment == segment
                    ? Color.cyan.opacity(0.3)
                    : Color.clear
            )
            .clipShape(RoundedRectangle(cornerRadius: 8))
        }
        .buttonStyle(.plain)
    }
    
    // MARK: - Content View
    
    @ViewBuilder
    private var contentView: some View {
        switch selectedSegment {
        case .messages:
            MessagesView()
        case .sessions:
            SessionsView()
        case .output:
            AgentOutputView()
        }
    }
}

#Preview {
    ActivityView()
        .environmentObject(MonitorViewModel())
        .preferredColorScheme(.dark)
}
