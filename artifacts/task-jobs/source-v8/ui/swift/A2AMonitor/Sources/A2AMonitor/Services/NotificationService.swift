import Foundation

#if os(iOS)
import UIKit
import UserNotifications
#endif

/// Handles local user notifications for incoming monitor messages.
///
/// Note: This is *not* APNs push. It can only alert when the app is running
/// (foreground/background) and actively receiving events.
final class NotificationService {
    static let shared = NotificationService()

    private init() {}

    /// Simple in-memory de-dupe so reconnects / refreshes don't spam notifications.
    private var recentlyNotifiedMessageIds: [String] = []
    private let maxRecentIds = 200

    #if os(iOS)
    private let center = UNUserNotificationCenter.current()
    #endif

    // MARK: - Settings

    /// Global enable switch for alerts.
    /// Stored in UserDefaults so it can be toggled from settings UI later.
    @MainActor
    var isEnabled: Bool {
        get { UserDefaults.standard.object(forKey: "notificationsEnabled") as? Bool ?? true }
        set { UserDefaults.standard.set(newValue, forKey: "notificationsEnabled") }
    }

    /// If true, only notify for agent messages (recommended).
    @MainActor
    var agentOnly: Bool {
        get { UserDefaults.standard.object(forKey: "notificationsAgentOnly") as? Bool ?? true }
        set { UserDefaults.standard.set(newValue, forKey: "notificationsAgentOnly") }
    }

    // MARK: - Lifecycle

    func configure() {
        #if os(iOS)
        center.delegate = NotificationDelegate.shared
        #endif
    }

    func requestAuthorizationIfNeeded() async {
        #if os(iOS)
        let settings = await center.notificationSettings()
        switch settings.authorizationStatus {
        case .notDetermined:
            _ = try? await center.requestAuthorization(options: [.alert, .badge, .sound])
        case .denied, .authorized, .provisional, .ephemeral:
            break
        @unknown default:
            break
        }
        #endif
    }

    // MARK: - Notifications

    @MainActor
    func notifyIfNeeded(for message: Message) {
        guard isEnabled else { return }

        // Only notify on agent messages by default (avoid noisy system/tool chatter).
        if agentOnly, message.type != .agent {
            return
        }

        let messageId = message.id
        if recentlyNotifiedMessageIds.contains(messageId) {
            return
        }

        recentlyNotifiedMessageIds.append(messageId)
        if recentlyNotifiedMessageIds.count > maxRecentIds {
            recentlyNotifiedMessageIds.removeFirst(recentlyNotifiedMessageIds.count - maxRecentIds)
        }

        #if os(iOS)
        scheduleLocalNotification(for: message)
        #endif
    }

    @MainActor
    func sendTestNotification() {
        #if os(iOS)
        let msg = Message(
            id: UUID().uuidString,
            timestamp: Date(),
            type: .agent,
            agentName: "A2A Agent",
            content: "Test alert: an agent message arrived."
        )
        scheduleLocalNotification(for: msg)
        #endif
    }

    #if os(iOS)
    private func scheduleLocalNotification(for message: Message) {
        let content = UNMutableNotificationContent()
        content.title = message.agentName.isEmpty ? "New agent message" : message.agentName

        let body = message.content.trimmingCharacters(in: .whitespacesAndNewlines)
        content.body = body.isEmpty ? "(No content)" : body
        content.sound = .default

        // Best-effort badge increment.
        let current = UIApplication.shared.applicationIconBadgeNumber
        content.badge = NSNumber(value: current + 1)

        // Fire immediately.
        let request = UNNotificationRequest(
            identifier: "a2a.monitor.message.\(message.id)",
            content: content,
            trigger: nil
        )

        center.add(request) { _ in }
    }
    #endif
}

#if os(iOS)
/// Presents notifications as banners even when the app is in the foreground.
final class NotificationDelegate: NSObject, UNUserNotificationCenterDelegate {
    static let shared = NotificationDelegate()

    private override init() {}

    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification
    ) async -> UNNotificationPresentationOptions {
        // Show as banner while the app is open.
        return [.banner, .sound, .badge]
    }

    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse
    ) async {
        // Future enhancement: deep-link into Messages/Sessions.
    }
}
#endif
