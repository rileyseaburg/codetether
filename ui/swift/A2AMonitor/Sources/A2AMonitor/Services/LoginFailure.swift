import Foundation

/// Translate expected authentication failures without exposing raw server output.
enum LoginFailure {
    static func message(status: Int, data: Data) -> String {
        let body = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any]
        let detail = (body?["detail"] as? String ?? "").lowercased()
        if status == 401 || status == 400 {
            if detail.hasPrefix("invalid token:") || detail.contains("token validation failed") {
                return "The server could not validate your sign-in session. Please retry; if this continues, contact your administrator."
            }
            if detail.contains("account is not fully set up") || detail.contains("email not verified") {
                return "Your account needs setup. Verify your email and complete any required account setup in Keycloak, then sign in again."
            }
            if detail.contains("account disabled") || detail.contains("user is disabled") {
                return "This account is disabled. Contact your administrator."
            }
            if detail.contains("direct access grants") || detail.contains("client credentials") {
                return "The server's sign-in configuration needs attention. Contact your administrator."
            }
            if status == 401 {
                return "Invalid email or password. Use the email address registered with Keycloak."
            }
        }
        if status == 429 {
            return "Too many sign-in attempts. Wait a moment before trying again."
        }
        if status == 503 {
            return "Sign-in is temporarily unavailable. Please try again shortly."
        }
        return "Sign-in failed (HTTP \(status)). Try again or contact your administrator."
    }
}