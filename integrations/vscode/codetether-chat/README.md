# CodeTether Chat (VS Code)

This VS Code extension contributes a `@CodeTether` chat participant and uploads each chat turn to your CodeTether server as a Session.

## Setup

1. Start your CodeTether server (default `http://localhost:8000`).
2. In VS Code settings:
   - Set `codetether.apiUrl`
   - Optionally set `codetether.apiToken` (Bearer token value from `A2A_AUTH_TOKENS`)
3. Run the command `CodeTether: Pick Codebase` and select the codebase that matches your workspace.

## Usage

Open the Chat view and talk to `@CodeTether`. Each conversation becomes a session in the CodeTether dashboard Sessions page.

## Notes

- VS Code's chat extension API only exposes history for the current participant; it cannot read Copilot's built-in chat history. This extension captures the turns you have with `@CodeTether`.
- Token counts are best-effort via `LanguageModelChat.countTokens` (cost is not available via the VS Code API).

