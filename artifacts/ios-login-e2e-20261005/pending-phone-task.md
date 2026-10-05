# Pending phone-submitted HTML proof task

This is prepared task text, **not evidence of submission or execution**.

After installing the prepared build and manual sign-in:
1. Open **Command → Tasks & Responses → Create Task**.
2. Select **iOS E2E - ubuntu-dev** (`ios-e2e-ubuntu-dev`).
3. Enter a unique title and the task text below. Leave agent type **Build**.
   Set **Model** to `github-copilot/gpt-5-mini`, the backend-tested provider/model.
4. Submit once. Record the returned task ID from its card.
5. Open **View response** on that card. The response screen polls that same ID.

This path uses the task API, not the separate voice-trigger/Knative path.

> Create a small HTML page in this workspace's `site/index.html` with the title
> "A2A iPhone to local agent". Include the actual task ID, a UTC creation timestamp,
> and a visible confirmation that the task came from the native iPhone app.
> Do not claim phone provenance unless it is present in the task context.
>
> Host ONLY this site directory at `http://192.168.50.101:8766/` on this server.
> Check that the port is free first. Use a small Node HTTP server or an existing
> suitable static-file server; reject paths outside the site directory. Keep it
> running with a named user service. Do not alter camera services on ports 80/443,
> existing tunnels, authentication, unrelated files, or running services.
>
> Verify a GET returns HTTP 200 and the task-specific page content. Reply to this
> task with the URL, exact file path, SHA-256, and service/process identity. Never
> include credentials, tokens, or private configuration in the page or response.