# Page snapshot

```yaml
- generic [active] [ref=e1]:
  - main [ref=e2]:
    - generic [ref=e3]:
      - link "Home" [ref=e4] [cursor=pointer]:
        - /url: /
        - img [ref=e5]:
          - generic [ref=e11]: CodeTether
      - generic [ref=e12]:
        - img [ref=e13]
        - heading "Sign in to account" [level=1] [ref=e18]
        - paragraph [ref=e19]:
          - text: Don't have an account?
          - link "Sign up" [ref=e20] [cursor=pointer]:
            - /url: /register
          - text: for a free trial.
      - generic [ref=e21]:
        - button "Continue with Quantum Forge SSO" [ref=e22]:
          - img [ref=e23]
          - text: Continue with Quantum Forge SSO
        - generic [ref=e29]: Or continue with email
        - generic [ref=e30]:
          - generic [ref=e31]:
            - generic [ref=e32]:
              - generic [ref=e33]: Email address
              - textbox "Email address" [ref=e34]
            - generic [ref=e35]:
              - generic [ref=e36]: Password
              - textbox "Password" [ref=e37]
          - button "Sign in to account" [ref=e38]
  - alert [ref=e39]
```