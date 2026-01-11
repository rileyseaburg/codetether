import SwiftUI

// MARK: - Onboarding View

struct OnboardingView: View {
    @Binding var hasSeenOnboarding: Bool
    @State private var currentPage = 0
    
    private let pages: [OnboardingPage] = [
        OnboardingPage(
            icon: "cpu.fill",
            iconColor: .cyan,
            title: "Control Your AI Agents",
            subtitle: "Your command center for AI coding assistants",
            features: [
                OnboardingFeature(icon: "eye.fill", text: "Monitor AI coding agents in real-time"),
                OnboardingFeature(icon: "hand.raised.fill", text: "See what they're doing and intervene when needed"),
                OnboardingFeature(icon: "bell.badge.fill", text: "Get notified of important events")
            ]
        ),
        OnboardingPage(
            icon: "gearshape.2.fill",
            iconColor: Color.liquidGlass.primary,
            title: "How It Works",
            subtitle: "Three simple steps to get started",
            features: [
                OnboardingFeature(icon: "folder.fill", text: "Connect your codebase (a folder with your code)"),
                OnboardingFeature(icon: "bolt.fill", text: "Trigger an AI agent to work on a task"),
                OnboardingFeature(icon: "chart.line.uptrend.xyaxis", text: "Monitor progress and guide when needed")
            ],
            showStepNumbers: true
        ),
        OnboardingPage(
            icon: "sparkles",
            iconColor: Color.liquidGlass.success,
            title: "Let's Get Started",
            subtitle: "You're ready to take control",
            features: [
                OnboardingFeature(icon: "checkmark.shield.fill", text: "Your AI agents, your rules"),
                OnboardingFeature(icon: "bolt.horizontal.fill", text: "Fast, beautiful, and powerful"),
                OnboardingFeature(icon: "arrow.right.circle.fill", text: "Tap Continue to begin")
            ]
        )
    ]
    
    var body: some View {
        ZStack {
            // Background
            LiquidGradientBackground()
            
            VStack(spacing: 0) {
                // Skip button
                HStack {
                    Spacer()
                    Button("Skip") {
                        withAnimation(.spring(response: 0.4, dampingFraction: 0.8)) {
                            hasSeenOnboarding = true
                        }
                    }
                    .font(.subheadline)
                    .fontWeight(.medium)
                    .foregroundColor(Color.liquidGlass.textSecondary)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 8)
                    .background(.ultraThinMaterial)
                    .clipShape(Capsule())
                }
                .padding(.horizontal, 24)
                .padding(.top, 16)
                
                // Page content
                TabView(selection: $currentPage) {
                    ForEach(Array(pages.enumerated()), id: \.offset) { index, page in
                        OnboardingPageView(page: page)
                            .tag(index)
                    }
                }
                .tabViewStyle(.page(indexDisplayMode: .never))
                .animation(.easeInOut(duration: 0.3), value: currentPage)
                
                // Bottom section
                VStack(spacing: 24) {
                    // Page indicator dots
                    HStack(spacing: 12) {
                        ForEach(0..<pages.count, id: \.self) { index in
                            Circle()
                                .fill(index == currentPage ? Color.cyan : Color.white.opacity(0.3))
                                .frame(width: index == currentPage ? 10 : 8, height: index == currentPage ? 10 : 8)
                                .scaleEffect(index == currentPage ? 1.2 : 1.0)
                                .animation(.spring(response: 0.3, dampingFraction: 0.7), value: currentPage)
                        }
                    }
                    
                    // Action button
                    Button {
                        withAnimation(.spring(response: 0.4, dampingFraction: 0.8)) {
                            if currentPage < pages.count - 1 {
                                currentPage += 1
                            } else {
                                hasSeenOnboarding = true
                            }
                        }
                    } label: {
                        HStack(spacing: 8) {
                            Text(currentPage == pages.count - 1 ? "Get Started" : "Continue")
                                .fontWeight(.semibold)
                            
                            Image(systemName: currentPage == pages.count - 1 ? "arrow.right" : "chevron.right")
                                .font(.subheadline.weight(.semibold))
                        }
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 18)
                        .background(
                            LinearGradient(
                                colors: [Color.liquidGlass.primary, Color.liquidGlass.secondary],
                                startPoint: .leading,
                                endPoint: .trailing
                            )
                        )
                        .clipShape(RoundedRectangle(cornerRadius: 16))
                        .shadow(color: Color.liquidGlass.primary.opacity(0.4), radius: 12, x: 0, y: 6)
                    }
                    .buttonStyle(.plain)
                    .padding(.horizontal, 32)
                }
                .padding(.bottom, 48)
            }
        }
    }
}

// MARK: - Onboarding Page View

struct OnboardingPageView: View {
    let page: OnboardingPage
    @State private var appeared = false
    
    var body: some View {
        VStack(spacing: 32) {
            Spacer()
            
            // Icon
            ZStack {
                // Glow effect
                Circle()
                    .fill(page.iconColor.opacity(0.2))
                    .frame(width: 140, height: 140)
                    .blur(radius: 30)
                
                // Icon background
                Circle()
                    .fill(.ultraThinMaterial)
                    .frame(width: 120, height: 120)
                    .overlay(
                        Circle()
                            .stroke(
                                LinearGradient(
                                    colors: [Color.white.opacity(0.3), Color.white.opacity(0.1)],
                                    startPoint: .topLeading,
                                    endPoint: .bottomTrailing
                                ),
                                lineWidth: 1
                            )
                    )
                
                // Icon
                Image(systemName: page.icon)
                    .font(.system(size: 50))
                    .foregroundStyle(
                        LinearGradient(
                            colors: [page.iconColor, page.iconColor.opacity(0.7)],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
            }
            .scaleEffect(appeared ? 1.0 : 0.5)
            .opacity(appeared ? 1.0 : 0.0)
            
            // Text content
            VStack(spacing: 12) {
                Text(page.title)
                    .font(.system(size: 28, weight: .bold, design: .rounded))
                    .foregroundColor(Color.liquidGlass.textPrimary)
                    .multilineTextAlignment(.center)
                
                Text(page.subtitle)
                    .font(.body)
                    .foregroundColor(Color.liquidGlass.textSecondary)
                    .multilineTextAlignment(.center)
            }
            .offset(y: appeared ? 0 : 20)
            .opacity(appeared ? 1.0 : 0.0)
            
            // Feature list
            VStack(spacing: 16) {
                ForEach(Array(page.features.enumerated()), id: \.element.id) { index, feature in
                    HStack(spacing: 16) {
                        // Step number or icon
                        ZStack {
                            Circle()
                                .fill(Color.white.opacity(0.1))
                                .frame(width: 44, height: 44)
                            
                            if page.showStepNumbers {
                                Text("\(index + 1)")
                                    .font(.headline)
                                    .fontWeight(.bold)
                                    .foregroundColor(.cyan)
                            } else {
                                Image(systemName: feature.icon)
                                    .font(.body)
                                    .foregroundColor(.cyan)
                            }
                        }
                        
                        Text(feature.text)
                            .font(.subheadline)
                            .foregroundColor(Color.liquidGlass.textPrimary)
                            .multilineTextAlignment(.leading)
                        
                        Spacer()
                    }
                    .padding(.horizontal, 20)
                    .padding(.vertical, 12)
                    .background(
                        RoundedRectangle(cornerRadius: 14)
                            .fill(.ultraThinMaterial)
                            .overlay(
                                RoundedRectangle(cornerRadius: 14)
                                    .stroke(Color.white.opacity(0.1), lineWidth: 1)
                            )
                    )
                    .offset(y: appeared ? 0 : CGFloat(20 + index * 10))
                    .opacity(appeared ? 1.0 : 0.0)
                }
            }
            .padding(.horizontal, 24)
            
            Spacer()
            Spacer()
        }
        .onAppear {
            withAnimation(.spring(response: 0.6, dampingFraction: 0.8).delay(0.1)) {
                appeared = true
            }
        }
        .onDisappear {
            appeared = false
        }
    }
}

// MARK: - Data Models

struct OnboardingPage {
    let icon: String
    let iconColor: Color
    let title: String
    let subtitle: String
    let features: [OnboardingFeature]
    var showStepNumbers: Bool = false
}

struct OnboardingFeature: Identifiable {
    let id = UUID()
    let icon: String
    let text: String
}

// MARK: - Preview

#Preview {
    OnboardingView(hasSeenOnboarding: .constant(false))
}
