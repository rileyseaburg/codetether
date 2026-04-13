from urllib.parse import urlparse

from fastapi import HTTPException

from ..keycloak_auth import UserSession

_REALM_SUFFIX = '.codetether.run'


def ensure_tenant_access(user: UserSession, tenant_id: str) -> None:
    is_super_admin = 'super-admin' in user.roles
    if not is_super_admin and user.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail='Tenant access denied')


def org_slug_from_tenant(tenant: dict) -> str:
    realm_name = str(tenant.get('realm_name') or '').strip()
    if realm_name.endswith(_REALM_SUFFIX):
        org_slug = realm_name[: -len(_REALM_SUFFIX)].strip()
        if org_slug:
            return org_slug

    external_url = str(tenant.get('k8s_external_url') or '').strip()
    if external_url:
        host = urlparse(external_url).hostname or ''
        if host.endswith(_REALM_SUFFIX):
            org_slug = host[: -len(_REALM_SUFFIX)].strip('.')
            if org_slug:
                return org_slug

    namespace = str(tenant.get('k8s_namespace') or '').strip()
    if namespace.startswith('tenant-'):
        org_slug = namespace[len('tenant-') :].strip()
        if org_slug:
            return org_slug

    raise HTTPException(
        status_code=400,
        detail='Tenant deployment is missing a resolvable organization slug',
    )
