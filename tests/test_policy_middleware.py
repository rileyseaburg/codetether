"""
Tests for the PolicyAuthorizationMiddleware path matching.

Verifies that all route patterns map to the correct permission strings.
"""

import pytest
from a2a_server.policy_middleware import _match_permission


class TestPublicRoutes:
    """Routes that should skip authorization (return empty string)."""

    def test_health(self):
        assert _match_permission("/health", "GET") == ""

    def test_well_known_agent_card(self):
        assert _match_permission("/.well-known/agent-card.json", "GET") == ""

    def test_docs(self):
        assert _match_permission("/docs", "GET") == ""

    def test_openapi(self):
        assert _match_permission("/openapi.json", "GET") == ""

    def test_auth_login(self):
        assert _match_permission("/v1/auth/login", "POST") == ""

    def test_auth_refresh(self):
        assert _match_permission("/v1/auth/refresh", "POST") == ""

    def test_nextauth(self):
        assert _match_permission("/api/auth/session", "GET") == ""
        assert _match_permission("/api/auth/csrf", "GET") == ""

    def test_user_register(self):
        assert _match_permission("/v1/users/register", "POST") == ""

    def test_user_login(self):
        assert _match_permission("/v1/users/login", "POST") == ""

    def test_password_reset(self):
        assert _match_permission("/v1/users/password-reset/request", "POST") == ""

    def test_tenant_signup(self):
        assert _match_permission("/v1/tenants/signup", "POST") == ""

    def test_stripe_webhook(self):
        assert _match_permission("/v1/webhooks/stripe", "POST") == ""


class TestAlreadyProtectedRoutes:
    """Routes with existing auth deps — middleware skips them."""

    def test_billing(self):
        assert _match_permission("/v1/billing/setup", "POST") == ""
        assert _match_permission("/v1/billing/subscription", "GET") == ""

    def test_admin(self):
        assert _match_permission("/v1/admin/dashboard", "GET") == ""
        assert _match_permission("/v1/admin/users", "GET") == ""

    def test_tenant_management(self):
        assert _match_permission("/v1/tenants/me", "GET") == ""

    def test_user_auth(self):
        assert _match_permission("/v1/users/me", "GET") == ""
        assert _match_permission("/v1/users/api-keys", "GET") == ""

    def test_cronjobs(self):
        assert _match_permission("/v1/cronjobs", "GET") == ""

    def test_queue(self):
        assert _match_permission("/v1/queue/my", "GET") == ""


class TestMonitorRouter:
    def test_monitor_root_read(self):
        assert _match_permission("/v1/monitor", "GET") == "monitor:read"
        assert _match_permission("/v1/monitor/", "GET") == "monitor:read"

    def test_monitor_agents(self):
        assert _match_permission("/v1/monitor/agents", "GET") == "monitor:read"

    def test_monitor_messages(self):
        assert _match_permission("/v1/monitor/messages", "GET") == "monitor:read"
        assert _match_permission("/v1/monitor/messages/search", "GET") == "monitor:read"

    def test_monitor_stream(self):
        assert _match_permission("/v1/monitor/stream", "GET") == "monitor:read"

    def test_monitor_intervene_write(self):
        assert _match_permission("/v1/monitor/intervene", "POST") == "monitor:write"

    def test_monitor_export(self):
        assert _match_permission("/v1/monitor/export/json", "GET") == "monitor:read"
        assert _match_permission("/v1/monitor/export/csv", "GET") == "monitor:read"


class TestAgentRouterAdmin:
    def test_database_endpoints(self):
        assert _match_permission("/v1/agent/database/status", "GET") == "admin:access"
        assert _match_permission("/v1/agent/database/sessions", "GET") == "admin:access"
        assert _match_permission("/v1/agent/database/codebases", "GET") == "admin:access"

    def test_deduplicate(self):
        assert _match_permission("/v1/agent/database/codebases/deduplicate", "POST") == "admin:access"

    def test_stuck_tasks(self):
        assert _match_permission("/v1/agent/tasks/stuck", "GET") == "admin:access"
        assert _match_permission("/v1/agent/tasks/stuck/recover", "POST") == "admin:access"

    def test_reaper(self):
        assert _match_permission("/v1/agent/reaper/health", "GET") == "admin:access"

    def test_vault(self):
        assert _match_permission("/v1/agent/vault/status", "GET") == "api_keys:read"
        assert _match_permission("/v1/agent/vault/config", "GET") == "admin:access"


class TestAgentRouterCodebases:
    def test_create(self):
        assert _match_permission("/v1/agent/codebases", "POST") == "codebases:write"

    def test_list(self):
        assert _match_permission("/v1/agent/codebases", "GET") == "codebases:read"
        assert _match_permission("/v1/agent/codebases/list", "GET") == "codebases:read"

    def test_get_one(self):
        assert _match_permission("/v1/agent/codebases/abc123", "GET") == "codebases:read"

    def test_delete(self):
        assert _match_permission("/v1/agent/codebases/abc123", "DELETE") == "codebases:delete"

    def test_trigger(self):
        assert _match_permission("/v1/agent/codebases/abc123/trigger", "POST") == "codebases:write"

    def test_message(self):
        assert _match_permission("/v1/agent/codebases/abc123/message", "POST") == "codebases:write"

    def test_upload(self):
        assert _match_permission("/v1/agent/codebases/abc123/upload", "POST") == "codebases:write"

    def test_download(self):
        assert _match_permission("/v1/agent/codebases/abc123/download", "GET") == "codebases:read"


class TestAgentRouterTasks:
    def test_create(self):
        assert _match_permission("/v1/agent/tasks", "POST") == "tasks:write"

    def test_list(self):
        # Worker task polling — auth handled by WORKER_AUTH_TOKEN, not OPA
        assert _match_permission("/v1/agent/tasks", "GET") == ""

    def test_get_one(self):
        assert _match_permission("/v1/agent/tasks/task-123", "GET") == "tasks:read"

    def test_cancel(self):
        assert _match_permission("/v1/agent/tasks/task-123/cancel", "POST") == "tasks:write"

    def test_update_status(self):
        assert _match_permission("/v1/agent/tasks/task-123/status", "PUT") == "tasks:write"

    def test_output_write(self):
        assert _match_permission("/v1/agent/tasks/task-123/output", "POST") == "tasks:write"

    def test_output_read(self):
        assert _match_permission("/v1/agent/tasks/task-123/output", "GET") == "tasks:read"

    def test_requeue(self):
        assert _match_permission("/v1/agent/tasks/task-123/requeue", "POST") == "tasks:write"


class TestAgentRouterWorkers:
    def test_register(self):
        # Worker registration is internal infrastructure — skipped
        assert _match_permission("/v1/agent/workers/register", "POST") == ""

    def test_unregister(self):
        assert _match_permission("/v1/agent/workers/w1/unregister", "POST") == ""

    def test_list(self):
        assert _match_permission("/v1/agent/workers", "GET") == ""

    def test_get_one(self):
        assert _match_permission("/v1/agent/workers/w1", "GET") == ""

    def test_heartbeat(self):
        assert _match_permission("/v1/agent/workers/w1/heartbeat", "POST") == ""


class TestAgentRouterSessions:
    def test_list(self):
        assert _match_permission("/v1/agent/codebases/cb1/sessions", "GET") == "sessions:read"

    def test_ingest(self):
        assert _match_permission("/v1/agent/codebases/cb1/sessions/s1/ingest", "POST") == "sessions:write"

    def test_sync(self):
        assert _match_permission("/v1/agent/codebases/cb1/sessions/sync", "POST") == "sessions:write"

    def test_resume(self):
        assert _match_permission("/v1/agent/codebases/cb1/sessions/s1/resume", "POST") == "sessions:write"


class TestAgentRouterApiKeys:
    def test_list(self):
        assert _match_permission("/v1/agent/api-keys", "GET") == "api_keys:read"

    def test_create(self):
        assert _match_permission("/v1/agent/api-keys", "POST") == "api_keys:write"

    def test_delete(self):
        assert _match_permission("/v1/agent/api-keys/provider-1", "DELETE") == "api_keys:delete"

    def test_sync(self):
        assert _match_permission("/v1/agent/api-keys/sync", "GET") == "api_keys:read"


class TestVoiceRouter:
    def test_list_voices(self):
        assert _match_permission("/v1/voice/voices", "GET") == "voice:read"

    def test_create_session(self):
        assert _match_permission("/v1/voice/sessions", "POST") == "voice:write"

    def test_delete_session(self):
        assert _match_permission("/v1/voice/sessions/room1", "DELETE") == "voice:delete"

    def test_get_session(self):
        assert _match_permission("/v1/voice/sessions/room1", "GET") == "voice:read"


class TestRalphRouter:
    def test_create_run(self):
        assert _match_permission("/v1/ralph/runs", "POST") == "ralph:write"

    def test_list_runs(self):
        assert _match_permission("/v1/ralph/runs", "GET") == "ralph:read"

    def test_cancel_run(self):
        assert _match_permission("/v1/ralph/runs/r1/cancel", "POST") == "ralph:write"

    def test_delete_run(self):
        assert _match_permission("/v1/ralph/runs/r1", "DELETE") == "ralph:delete"

    def test_chat(self):
        assert _match_permission("/v1/ralph/chat", "POST") == "ralph:write"


class TestEmailRouter:
    def test_inbound_webhook(self):
        assert _match_permission("/v1/email/inbound", "POST") == "email:write"

    def test_admin_endpoints(self):
        assert _match_permission("/v1/email/test", "POST") == "email:admin"
        assert _match_permission("/v1/email/preview", "POST") == "email:admin"
        assert _match_permission("/v1/email/test/send", "POST") == "email:admin"


class TestAnalyticsRouter:
    def test_tracking(self):
        assert _match_permission("/v1/analytics/track", "POST") == "analytics:write"
        assert _match_permission("/v1/analytics/identify", "POST") == "analytics:write"

    def test_admin_views(self):
        assert _match_permission("/v1/analytics/funnel", "GET") == "analytics:admin"
        assert _match_permission("/v1/analytics/attribution/user1", "GET") == "analytics:admin"


class TestMCPRouter:
    """MCP is an internal agent protocol — skips middleware auth (like /a2a/)."""

    def test_rpc_write(self):
        assert _match_permission("/mcp/v1/rpc", "POST") == ""

    def test_message_write(self):
        assert _match_permission("/mcp/v1/message", "POST") == ""

    def test_tasks_write(self):
        assert _match_permission("/mcp/v1/tasks", "POST") == ""

    def test_tasks_read(self):
        assert _match_permission("/mcp/v1/tasks", "GET") == ""

    def test_root_read(self):
        assert _match_permission("/mcp", "GET") == ""

    def test_sse(self):
        assert _match_permission("/mcp/v1/sse", "GET") == ""


class TestAuthRouterProtectedEndpoints:
    def test_session(self):
        assert _match_permission("/v1/auth/session", "GET") == "sessions:read"

    def test_sync(self):
        assert _match_permission("/v1/auth/sync", "GET") == "sessions:read"

    def test_user_codebases_read(self):
        assert _match_permission("/v1/auth/user/u1/codebases", "GET") == "codebases:read"

    def test_user_codebases_write(self):
        assert _match_permission("/v1/auth/user/u1/codebases", "POST") == "codebases:write"

    def test_user_codebases_delete(self):
        assert _match_permission("/v1/auth/user/u1/codebases/cb1", "DELETE") == "codebases:delete"

    def test_user_sessions(self):
        assert _match_permission("/v1/auth/user/u1/agent-sessions", "GET") == "sessions:read"


class TestProactiveRouter:
    """Proactive rule engine endpoints."""

    def test_create_rule(self):
        assert _match_permission("/v1/proactive/rules", "POST") == "proactive:write"

    def test_list_rules(self):
        assert _match_permission("/v1/proactive/rules", "GET") == "proactive:read"

    def test_get_rule(self):
        assert _match_permission("/v1/proactive/rules/r1", "GET") == "proactive:read"

    def test_update_rule(self):
        assert _match_permission("/v1/proactive/rules/r1", "PUT") == "proactive:write"

    def test_delete_rule(self):
        assert _match_permission("/v1/proactive/rules/r1", "DELETE") == "proactive:delete"

    def test_rule_runs(self):
        assert _match_permission("/v1/proactive/rules/r1/runs", "GET") == "proactive:read"

    def test_create_health_check(self):
        assert _match_permission("/v1/proactive/health-checks", "POST") == "proactive:write"

    def test_list_health_checks(self):
        assert _match_permission("/v1/proactive/health-checks", "GET") == "proactive:read"

    def test_get_health_check(self):
        assert _match_permission("/v1/proactive/health-checks/hc1", "GET") == "proactive:read"

    def test_update_health_check(self):
        assert _match_permission("/v1/proactive/health-checks/hc1", "PUT") == "proactive:write"

    def test_delete_health_check(self):
        assert _match_permission("/v1/proactive/health-checks/hc1", "DELETE") == "proactive:delete"

    def test_create_loop(self):
        assert _match_permission("/v1/proactive/loops", "POST") == "proactive:write"

    def test_list_loops(self):
        assert _match_permission("/v1/proactive/loops", "GET") == "proactive:read"

    def test_get_loop(self):
        assert _match_permission("/v1/proactive/loops/l1", "GET") == "proactive:read"

    def test_update_loop(self):
        assert _match_permission("/v1/proactive/loops/l1", "PUT") == "proactive:write"

    def test_delete_loop(self):
        assert _match_permission("/v1/proactive/loops/l1", "DELETE") == "proactive:delete"

    def test_loop_iterations(self):
        assert _match_permission("/v1/proactive/loops/l1/iterations", "GET") == "proactive:read"

    def test_decisions(self):
        assert _match_permission("/v1/proactive/decisions", "GET") == "decisions:read"

    def test_status(self):
        assert _match_permission("/v1/proactive/status", "GET") == "proactive:read"


class TestTokenBillingRouter:
    """Token billing endpoints."""

    def test_budget_write(self):
        assert _match_permission("/v1/token-billing/budgets", "POST") == "billing:write"

    def test_budget_update(self):
        assert _match_permission("/v1/token-billing/budgets/b1", "PUT") == "billing:write"

    def test_budget_delete(self):
        assert _match_permission("/v1/token-billing/budgets/b1", "DELETE") == "billing:write"

    def test_pricing_write(self):
        assert _match_permission("/v1/token-billing/pricing", "POST") == "billing:write"

    def test_usage_read(self):
        assert _match_permission("/v1/token-billing/usage", "GET") == "billing:read"

    def test_summary_read(self):
        assert _match_permission("/v1/token-billing/summary", "GET") == "billing:read"


class TestOpaEnabledToggle:
    """Test that OPA_ENABLED toggle disables enforcement."""

    def test_middleware_bypasses_when_disabled(self):
        """When OPA_ENABLED=false, check_policy always returns True."""
        import os
        import a2a_server.policy as policy_mod

        original = policy_mod.OPA_ENABLED
        try:
            policy_mod.OPA_ENABLED = False
            import asyncio
            result = asyncio.get_event_loop().run_until_complete(
                policy_mod.check_policy(
                    {"user_id": "nobody", "roles": []},
                    "admin:access",
                )
            )
            assert result is True
        finally:
            policy_mod.OPA_ENABLED = original
