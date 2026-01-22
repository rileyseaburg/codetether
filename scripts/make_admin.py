#!/usr/bin/env python3
"""
Make a user an admin in Keycloak.

Usage:
    python scripts/make_admin.py <email> [realm_name]

Examples:
    python scripts/make_admin.py info@evolvingsoftware.io
    python scripts/make_admin.py info@evolvingsoftware.io master
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from a2a_server.tenant_service import KeycloakTenantService


async def make_admin(email: str, realm_name: str = 'master'):
    """Assign admin role to user."""
    print(f'Assigning admin role to {email} in realm {realm_name}...')

    service = KeycloakTenantService()
    success = await service.assign_admin_role(realm_name, email)

    if success:
        print(f'SUCCESS: {email} is now an admin in realm {realm_name}')
        print(f'\nUser can now access:')
        print(f'  GET /v1/admin/dashboard')
        print(f'  GET /v1/admin/users')
        print(f'  GET /v1/admin/tenants')
        print(f'  GET /v1/admin/instances')
        print(f'  ... and other admin endpoints')
    else:
        print(f'FAILED: Could not assign admin role to {email}')
        print('\nPossible reasons:')
        print('  - User does not exist in the realm')
        print('  - Keycloak connection failed')
        print('  - Insufficient permissions')
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    email = sys.argv[1]
    realm_name = sys.argv[2] if len(sys.argv) > 2 else 'master'

    asyncio.run(make_admin(email, realm_name))


if __name__ == '__main__':
    main()
