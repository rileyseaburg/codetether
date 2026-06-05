"""Webhook subpackage: single-responsibility helpers for the GitHub App router.

The router module re-exports the FastAPI handler and delegates each gate to a
focused helper here. Keep each module under 80 lines and free of unrelated
imports.

Public helpers (imported by the router):
    ingest.read_event            - signature verify, body parse, ping shortcut
    ingest.is_ping_response      - type discriminator for read_event output
    filters.is_installation_scope_event
    filters.is_self_authored
    filters.has_actionable_event
    install_events.handle_installation_scope_event
    failed_checks.handle_failed_check
    mention_dispatch.handle_mention_event
    responses.{ignored, rejected, accepted}
"""
