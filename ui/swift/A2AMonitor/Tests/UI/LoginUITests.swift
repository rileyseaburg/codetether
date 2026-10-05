import XCTest

final class LoginUITests: XCTestCase {
    func testLoginFailureMessages() throws {
        let setup = try JSONSerialization.data(withJSONObject: ["detail": "Account is not fully set up"])
        XCTAssertTrue(LoginFailure.message(status: 401, data: setup).contains("Verify your email"))
        let disabled = try JSONSerialization.data(withJSONObject: ["detail": "Account disabled"])
        XCTAssertTrue(LoginFailure.message(status: 401, data: disabled).contains("disabled"))
        let client = try JSONSerialization.data(withJSONObject: ["detail": "Client not allowed for direct access grants"])
        XCTAssertTrue(LoginFailure.message(status: 401, data: client).contains("configuration"))
        let issuer = try JSONSerialization.data(withJSONObject: ["detail": "Invalid token: Invalid issuer"])
        let issuerMessage = LoginFailure.message(status: 401, data: issuer)
        XCTAssertTrue(issuerMessage.contains("validate your sign-in session"))
        XCTAssertFalse(issuerMessage.contains("Invalid email or password"))
        let credentials = try JSONSerialization.data(withJSONObject: ["detail": "Invalid user credentials"])
        XCTAssertTrue(LoginFailure.message(status: 401, data: credentials).contains("Invalid email or password"))
        let sensitive = try JSONSerialization.data(withJSONObject: ["detail": "private-upstream-diagnostic"])
        XCTAssertFalse(LoginFailure.message(status: 500, data: sensitive).contains("private-upstream"))
        XCTAssertTrue(LoginFailure.message(status: 429, data: Data()).contains("Too many"))
        XCTAssertTrue(LoginFailure.message(status: 503, data: Data()).contains("temporarily unavailable"))
        XCTAssertTrue(LoginFailure.message(status: 401, data: Data("not-json".utf8)).contains("Invalid email"))
    }

    func testInspectPhoneWithoutEnteringCredentials() {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launch()
        XCTAssertTrue(app.wait(for: .runningForeground, timeout: 30))
        let email = app.textFields["auth.email"]
        let signedIn = app.tabBars.buttons["Command"]
        let ready = email.waitForExistence(timeout: 15) || signedIn.waitForExistence(timeout: 5)
        let screenshot = XCTAttachment(screenshot: app.screenshot())
        screenshot.name = "a2a-monitor-phone-screen"
        screenshot.lifetime = .keepAlways
        add(screenshot)
        XCTAssertTrue(ready, "Expected native login screen or authenticated Command tab")
        if email.exists {
            XCTAssertTrue(app.secureTextFields["auth.password"].exists)
            XCTAssertTrue(app.buttons["auth.signIn"].exists)
            // Human sign-in is intentionally required; never type credentials here.
        } else {
            XCTAssertTrue(signedIn.exists)
        }
    }
}