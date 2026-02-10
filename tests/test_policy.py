"""
Integration tests for OPA policy engine.

Tests the local evaluation mode of the policy module to verify
that RBAC, API key scopes, tenant isolation, and resource ownership
are correctly enforced.

Run with: OPA_LOCAL_MODE=true pytest tests/test_policy.py -v
"""

import os
import asyncio
import pytest

# Force local mode so tests don't require an OPA sidecar.
os.environ["OPA_LOCAL_MODE"] = "true"

from a2a_server.policy import (
    check_policy,
    check_tenant_policy,
    enforce_policy,
    _evaluate_local,
    _detect_auth_source,
    _build_input,
)
from fastapi import HTTPException


# ── Fixtures ─────────────────────────────────────────────────────


def admin_user():
    return {
        "id": "user-admin",
        "user_id": "user-admin",
        "email": "admin@test.com",
        "roles": ["admin"],
        "tenant_id": "tenant-1",
    }


def a2a_admin_user():
    return {
        "id": "user-a2a-admin",
        "user_id": "user-a2a-admin",
        "email": "a2a-admin@test.com",
        "roles": ["a2a-admin"],
        "tenant_id": "tenant-1",
    }


def operator_user():
    return {
        "id": "user-operator",
        "user_id": "user-operator",
        "email": "operator@test.com",
        "roles": ["operator"],
        "tenant_id": "tenant-1",
    }


def editor_user():
    return {
        "id": "user-editor",
        "user_id": "user-editor",
        "email": "editor@test.com",
        "roles": ["editor"],
        "tenant_id": "tenant-1",
    }


def viewer_user():
    return {
        "id": "user-viewer",
        "user_id": "user-viewer",
        "email": "viewer@test.com",
        "roles": ["viewer"],
        "tenant_id": "tenant-1",
    }


def no_role_user():
    return {
        "id": "user-norole",
        "user_id": "user-norole",
        "email": "norole@test.com",
        "roles": [],
        "tenant_id": "tenant-1",
    }


def api_key_user_read_write():
    return {
        "id": "user-apikey",
        "user_id": "user-apikey",
        "email": "apikey@test.com",
        "roles": ["editor"],
        "tenant_id": "tenant-1",
        "api_key_scopes": ["tasks:read", "tasks:write"],
    }


def api_key_user_readonly():
    return {
        "id": "user-apikey-ro",
        "user_id": "user-apikey-ro",
        "email": "ro@test.com",
        "roles": ["editor"],
        "tenant_id": "tenant-1",
        "api_key_scopes": ["tasks:read"],
    }


# ── Auth source detection ────────────────────────────────────────


class TestAuthSourceDetection:
    def test_api_key_detected(self):
        assert _detect_auth_source(api_key_user_read_write()) == "api_key"

    def test_keycloak_detected(self):
        user = {"keycloak_sub": "sub-123"}
        assert _detect_auth_source(user) == "keycloak"

    def test_self_service_default(self):
        assert _detect_auth_source(editor_user()) == "self-service"


# ── Role-based access ───────────────────────────────────────────


class TestRoleBasedAccess:
    @pytest.mark.asyncio
    async def test_admin_full_access(self):
        assert await check_policy(admin_user(), "admin:access")
        assert await check_policy(admin_user(), "tasks:write")
        assert await check_policy(admin_user(), "codebases:delete")

    @pytest.mark.asyncio
    async def test_a2a_admin_inherits_admin(self):
        assert await check_policy(a2a_admin_user(), "admin:access")
        assert await check_policy(a2a_admin_user(), "admin:manage_users")

    @pytest.mark.asyncio
    async def test_operator_permissions(self):
        assert await check_policy(operator_user(), "tasks:read")
        assert await check_policy(operator_user(), "workers:write")
        assert not await check_policy(operator_user(), "admin:access")
        assert not await check_policy(operator_user(), "tasks:delete")

    @pytest.mark.asyncio
    async def test_editor_permissions(self):
        assert await check_policy(editor_user(), "tasks:write")
        assert await check_policy(editor_user(), "agent:execute")
        assert not await check_policy(editor_user(), "admin:access")
        assert not await check_policy(editor_user(), "workers:write")

    @pytest.mark.asyncio
    async def test_viewer_read_only(self):
        assert await check_policy(viewer_user(), "tasks:read")
        assert await check_policy(viewer_user(), "monitor:read")
        assert not await check_policy(viewer_user(), "tasks:write")
        assert not await check_policy(viewer_user(), "agent:execute")

    @pytest.mark.asyncio
    async def test_no_roles_denied(self):
        assert not await check_policy(no_role_user(), "tasks:read")

    @pytest.mark.asyncio
    async def test_public_endpoints_always_allowed(self):
        assert await check_policy(no_role_user(), "health")
        assert await check_policy(no_role_user(), "auth:login")
        assert await check_policy(no_role_user(), "auth:register")


# ── API key scope enforcement ────────────────────────────────────


class TestApiKeyScopes:
    @pytest.mark.asyncio
    async def test_in_scope_allowed(self):
        assert await check_policy(api_key_user_read_write(), "tasks:read")
        assert await check_policy(api_key_user_read_write(), "tasks:write")

    @pytest.mark.asyncio
    async def test_out_of_scope_denied(self):
        # editor role grants codebases:read, but api key scopes don't
        assert not await check_policy(api_key_user_read_write(), "codebases:read")

    @pytest.mark.asyncio
    async def test_readonly_key_denied_write(self):
        assert not await check_policy(api_key_user_readonly(), "tasks:write")

    @pytest.mark.asyncio
    async def test_readonly_key_allowed_read(self):
        assert await check_policy(api_key_user_readonly(), "tasks:read")


# ── Tenant isolation ─────────────────────────────────────────────


class TestTenantIsolation:
    @pytest.mark.asyncio
    async def test_same_tenant_allowed(self):
        resource = {"type": "task", "id": "t1", "tenant_id": "tenant-1"}
        assert await check_policy(editor_user(), "tasks:read", resource)

    @pytest.mark.asyncio
    async def test_cross_tenant_denied(self):
        resource = {"type": "task", "id": "t1", "tenant_id": "tenant-2"}
        assert not await check_policy(editor_user(), "tasks:read", resource)

    @pytest.mark.asyncio
    async def test_admin_cross_tenant_allowed(self):
        resource = {"type": "task", "id": "t1", "tenant_id": "tenant-2"}
        assert await check_policy(admin_user(), "tasks:read", resource)

    @pytest.mark.asyncio
    async def test_no_resource_tenant_defers(self):
        resource = {"type": "task", "id": "t1"}
        assert await check_policy(editor_user(), "tasks:read", resource)


# ── enforce_policy raises on denial ─────────────────────────────


class TestEnforcePolicy:
    @pytest.mark.asyncio
    async def test_enforce_allows_admin(self):
        await enforce_policy(admin_user(), "admin:access")  # should not raise

    @pytest.mark.asyncio
    async def test_enforce_denies_viewer_write(self):
        with pytest.raises(HTTPException) as exc_info:
            await enforce_policy(viewer_user(), "tasks:write")
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_enforce_denies_cross_tenant(self):
        resource = {"type": "task", "id": "t1", "tenant_id": "tenant-2"}
        with pytest.raises(HTTPException) as exc_info:
            await enforce_policy(editor_user(), "tasks:read", resource)
        assert exc_info.value.status_code == 403


# ── Input building ───────────────────────────────────────────────


class TestInputBuilding:
    def test_build_input_admin(self):
        inp = _build_input(admin_user(), "admin:access")
        assert inp["input"]["user"]["user_id"] == "user-admin"
        assert inp["input"]["action"] == "admin:access"
        assert "admin" in inp["input"]["user"]["roles"]

    def test_build_input_api_key(self):
        inp = _build_input(api_key_user_read_write(), "tasks:read")
        assert inp["input"]["user"]["auth_source"] == "api_key"
        assert "tasks:read" in inp["input"]["user"]["scopes"]
