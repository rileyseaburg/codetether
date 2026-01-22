"""
Keycloak Tenant Provisioning Service for A2A Server.

Provides multi-tenant provisioning capabilities:
- Create new realms for organizations
- Configure standard clients (SPA, API, Mobile)
- Manage admin users and roles
- Delete tenants
"""

import logging
import secrets
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

import httpx

from .keycloak_auth import (
    KEYCLOAK_URL,
    KEYCLOAK_ADMIN_USERNAME,
    KEYCLOAK_ADMIN_PASSWORD,
)

logger = logging.getLogger(__name__)


@dataclass
class TenantInfo:
    """Information about a provisioned tenant."""

    realm_name: str
    org_slug: str
    spa_client_id: str
    api_client_id: str
    api_client_secret: str
    mobile_client_id: str
    admin_user_id: str
    admin_email: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'realm_name': self.realm_name,
            'org_slug': self.org_slug,
            'client_ids': {
                'spa': self.spa_client_id,
                'api': self.api_client_id,
                'mobile': self.mobile_client_id,
            },
            'api_client_secret': self.api_client_secret,
            'admin_user_id': self.admin_user_id,
            'admin_email': self.admin_email,
        }


class KeycloakTenantServiceError(Exception):
    """Base exception for tenant service errors."""

    pass


class TenantAlreadyExistsError(KeycloakTenantServiceError):
    """Raised when attempting to create a tenant that already exists."""

    pass


class TenantNotFoundError(KeycloakTenantServiceError):
    """Raised when a tenant is not found."""

    pass


class KeycloakTenantService:
    """Manages Keycloak tenant (realm) provisioning."""

    # Standard redirect URIs and web origins for clients
    REDIRECT_URIS = [
        'http://localhost:*',
        'https://*.codetether.run/*',
        'https://app.codetether.run/*',
    ]
    WEB_ORIGINS = [
        'http://localhost:3000',
        'http://localhost:8080',
        'https://app.codetether.run',
        'https://*.codetether.run',
    ]

    def __init__(
        self,
        keycloak_url: str = KEYCLOAK_URL,
        admin_username: str = KEYCLOAK_ADMIN_USERNAME,
        admin_password: str = KEYCLOAK_ADMIN_PASSWORD,
    ):
        self.keycloak_url = keycloak_url.rstrip('/')
        self.admin_username = admin_username
        self.admin_password = admin_password
        self._admin_token: Optional[str] = None

        logger.info(
            f'KeycloakTenantService initialized for {self.keycloak_url}'
        )

    async def _get_admin_token(self) -> str:
        """Get admin access token from master realm using admin-cli client."""
        token_url = (
            f'{self.keycloak_url}/realms/master/protocol/openid-connect/token'
        )

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    token_url,
                    data={
                        'grant_type': 'password',
                        'client_id': 'admin-cli',
                        'username': self.admin_username,
                        'password': self.admin_password,
                    },
                    timeout=30.0,
                )
                response.raise_for_status()
                token_data = response.json()
                self._admin_token = token_data['access_token']
                logger.debug('Successfully obtained Keycloak admin token')
                return self._admin_token
            except httpx.HTTPStatusError as e:
                logger.error(
                    f'Failed to get admin token: {e.response.status_code}'
                )
                raise KeycloakTenantServiceError(
                    f'Failed to authenticate as admin: {e.response.text}'
                )
            except httpx.HTTPError as e:
                logger.error(f'HTTP error getting admin token: {e}')
                raise KeycloakTenantServiceError(
                    f'Failed to connect to Keycloak: {str(e)}'
                )

    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authorization headers with admin token."""
        if not self._admin_token:
            raise KeycloakTenantServiceError('Admin token not available')
        return {
            'Authorization': f'Bearer {self._admin_token}',
            'Content-Type': 'application/json',
        }

    async def create_tenant(
        self,
        org_slug: str,
        admin_email: str,
        admin_password: str,
        admin_first_name: str = 'Admin',
        admin_last_name: str = 'User',
    ) -> TenantInfo:
        """
        Create a new tenant (realm) in Keycloak.

        Args:
            org_slug: Organization slug (e.g., "acme") - will create realm "acme.codetether.run"
            admin_email: Email for the admin user
            admin_password: Password for the admin user
            admin_first_name: First name for the admin user
            admin_last_name: Last name for the admin user

        Returns:
            TenantInfo with realm details and client credentials
        """
        # Get fresh admin token
        await self._get_admin_token()

        realm_name = f'{org_slug}.codetether.run'
        logger.info(f'Creating tenant realm: {realm_name}')

        async with httpx.AsyncClient() as client:
            # Step 1: Create the realm
            await self._create_realm(client, realm_name, org_slug)

            # Step 2: Create standard clients
            spa_client_id = f'{org_slug}-spa'
            api_client_id = f'{org_slug}-api'
            mobile_client_id = f'{org_slug}-mobile'

            await self._create_spa_client(client, realm_name, spa_client_id)
            api_secret = await self._create_api_client(
                client, realm_name, api_client_id
            )
            await self._create_mobile_client(
                client, realm_name, mobile_client_id
            )

            # Step 3: Create admin role
            await self._create_role(
                client, realm_name, 'admin', 'Administrator role'
            )

            # Step 4: Create admin user
            admin_user_id = await self._create_user(
                client,
                realm_name,
                admin_email,
                admin_password,
                admin_first_name,
                admin_last_name,
            )

            # Step 5: Assign admin role to user
            await self._assign_role_to_user(
                client, realm_name, admin_user_id, 'admin'
            )

            logger.info(f'Successfully created tenant: {realm_name}')

            return TenantInfo(
                realm_name=realm_name,
                org_slug=org_slug,
                spa_client_id=spa_client_id,
                api_client_id=api_client_id,
                api_client_secret=api_secret,
                mobile_client_id=mobile_client_id,
                admin_user_id=admin_user_id,
                admin_email=admin_email,
            )

    async def _create_realm(
        self, client: httpx.AsyncClient, realm_name: str, org_slug: str
    ) -> None:
        """Create a new Keycloak realm."""
        realm_url = f'{self.keycloak_url}/admin/realms'

        realm_config = {
            'realm': realm_name,
            'enabled': True,
            'displayName': f'{org_slug.title()} - CodeTether',
            'displayNameHtml': f'<b>{org_slug.title()}</b> - CodeTether',
            'registrationAllowed': False,
            'registrationEmailAsUsername': True,
            'rememberMe': True,
            'verifyEmail': False,
            'loginWithEmailAllowed': True,
            'duplicateEmailsAllowed': False,
            'resetPasswordAllowed': True,
            'editUsernameAllowed': False,
            'bruteForceProtected': True,
            'permanentLockout': False,
            'maxFailureWaitSeconds': 900,
            'minimumQuickLoginWaitSeconds': 60,
            'waitIncrementSeconds': 60,
            'quickLoginCheckMilliSeconds': 1000,
            'maxDeltaTimeSeconds': 43200,
            'failureFactor': 30,
            'sslRequired': 'external',
            'accessTokenLifespan': 300,
            'accessTokenLifespanForImplicitFlow': 900,
            'ssoSessionIdleTimeout': 1800,
            'ssoSessionMaxLifespan': 36000,
            'offlineSessionIdleTimeout': 2592000,
            'accessCodeLifespan': 60,
            'accessCodeLifespanUserAction': 300,
            'accessCodeLifespanLogin': 1800,
        }

        try:
            response = await client.post(
                realm_url,
                json=realm_config,
                headers=self._get_auth_headers(),
                timeout=30.0,
            )

            if response.status_code == 409:
                raise TenantAlreadyExistsError(
                    f'Realm {realm_name} already exists'
                )

            response.raise_for_status()
            logger.info(f'Created realm: {realm_name}')

        except httpx.HTTPStatusError as e:
            if e.response.status_code != 409:
                logger.error(f'Failed to create realm: {e.response.text}')
                raise KeycloakTenantServiceError(
                    f'Failed to create realm: {e.response.text}'
                )
            raise

    async def _create_spa_client(
        self, client: httpx.AsyncClient, realm_name: str, client_id: str
    ) -> None:
        """Create a public SPA client."""
        clients_url = f'{self.keycloak_url}/admin/realms/{realm_name}/clients'

        client_config = {
            'clientId': client_id,
            'name': f'{client_id} - Web Application',
            'enabled': True,
            'publicClient': True,
            'standardFlowEnabled': True,
            'directAccessGrantsEnabled': True,
            'implicitFlowEnabled': False,
            'serviceAccountsEnabled': False,
            'authorizationServicesEnabled': False,
            'redirectUris': self.REDIRECT_URIS,
            'webOrigins': self.WEB_ORIGINS,
            'protocol': 'openid-connect',
            'attributes': {
                'pkce.code.challenge.method': 'S256',
                'post.logout.redirect.uris': '+',
            },
        }

        try:
            response = await client.post(
                clients_url,
                json=client_config,
                headers=self._get_auth_headers(),
                timeout=30.0,
            )
            response.raise_for_status()
            logger.info(f'Created SPA client: {client_id}')
        except httpx.HTTPStatusError as e:
            logger.error(f'Failed to create SPA client: {e.response.text}')
            raise KeycloakTenantServiceError(
                f'Failed to create SPA client: {e.response.text}'
            )

    async def _create_api_client(
        self, client: httpx.AsyncClient, realm_name: str, client_id: str
    ) -> str:
        """Create a confidential API client and return its secret."""
        clients_url = f'{self.keycloak_url}/admin/realms/{realm_name}/clients'

        # Generate a secure client secret
        client_secret = secrets.token_urlsafe(32)

        client_config = {
            'clientId': client_id,
            'name': f'{client_id} - Backend API',
            'enabled': True,
            'publicClient': False,
            'standardFlowEnabled': False,
            'directAccessGrantsEnabled': True,
            'serviceAccountsEnabled': True,
            'authorizationServicesEnabled': False,
            'secret': client_secret,
            'redirectUris': self.REDIRECT_URIS,
            'webOrigins': self.WEB_ORIGINS,
            'protocol': 'openid-connect',
            'attributes': {
                'client.secret.creation.time': '0',
            },
        }

        try:
            response = await client.post(
                clients_url,
                json=client_config,
                headers=self._get_auth_headers(),
                timeout=30.0,
            )
            response.raise_for_status()
            logger.info(f'Created API client: {client_id}')
            return client_secret
        except httpx.HTTPStatusError as e:
            logger.error(f'Failed to create API client: {e.response.text}')
            raise KeycloakTenantServiceError(
                f'Failed to create API client: {e.response.text}'
            )

    async def _create_mobile_client(
        self, client: httpx.AsyncClient, realm_name: str, client_id: str
    ) -> None:
        """Create a public mobile client."""
        clients_url = f'{self.keycloak_url}/admin/realms/{realm_name}/clients'

        client_config = {
            'clientId': client_id,
            'name': f'{client_id} - Mobile Application',
            'enabled': True,
            'publicClient': True,
            'standardFlowEnabled': True,
            'directAccessGrantsEnabled': True,
            'implicitFlowEnabled': False,
            'serviceAccountsEnabled': False,
            'authorizationServicesEnabled': False,
            'redirectUris': [
                'http://localhost:*',
                f'codetether://{client_id}/*',
                f'codetether.{client_id}://*',
            ],
            'webOrigins': ['*'],
            'protocol': 'openid-connect',
            'attributes': {
                'pkce.code.challenge.method': 'S256',
            },
        }

        try:
            response = await client.post(
                clients_url,
                json=client_config,
                headers=self._get_auth_headers(),
                timeout=30.0,
            )
            response.raise_for_status()
            logger.info(f'Created mobile client: {client_id}')
        except httpx.HTTPStatusError as e:
            logger.error(f'Failed to create mobile client: {e.response.text}')
            raise KeycloakTenantServiceError(
                f'Failed to create mobile client: {e.response.text}'
            )

    async def _create_role(
        self,
        client: httpx.AsyncClient,
        realm_name: str,
        role_name: str,
        description: str = '',
    ) -> None:
        """Create a realm role."""
        roles_url = f'{self.keycloak_url}/admin/realms/{realm_name}/roles'

        role_config = {
            'name': role_name,
            'description': description,
            'composite': False,
            'clientRole': False,
        }

        try:
            response = await client.post(
                roles_url,
                json=role_config,
                headers=self._get_auth_headers(),
                timeout=30.0,
            )
            response.raise_for_status()
            logger.info(f'Created role: {role_name} in realm {realm_name}')
        except httpx.HTTPStatusError as e:
            # Role might already exist
            if e.response.status_code != 409:
                logger.error(f'Failed to create role: {e.response.text}')
                raise KeycloakTenantServiceError(
                    f'Failed to create role: {e.response.text}'
                )
            logger.info(f'Role {role_name} already exists')

    async def _create_user(
        self,
        client: httpx.AsyncClient,
        realm_name: str,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
    ) -> str:
        """Create a user and return their ID."""
        users_url = f'{self.keycloak_url}/admin/realms/{realm_name}/users'

        user_config = {
            'username': email,
            'email': email,
            'firstName': first_name,
            'lastName': last_name,
            'enabled': True,
            'emailVerified': True,
            'credentials': [
                {
                    'type': 'password',
                    'value': password,
                    'temporary': False,
                }
            ],
        }

        try:
            response = await client.post(
                users_url,
                json=user_config,
                headers=self._get_auth_headers(),
                timeout=30.0,
            )
            response.raise_for_status()

            # Get user ID from Location header
            location = response.headers.get('Location', '')
            user_id = location.split('/')[-1] if location else ''

            if not user_id:
                # Fetch user by email to get ID
                search_response = await client.get(
                    users_url,
                    params={'email': email},
                    headers=self._get_auth_headers(),
                    timeout=30.0,
                )
                search_response.raise_for_status()
                users = search_response.json()
                if users:
                    user_id = users[0]['id']

            logger.info(f'Created user: {email} with ID {user_id}')
            return user_id

        except httpx.HTTPStatusError as e:
            logger.error(f'Failed to create user: {e.response.text}')
            raise KeycloakTenantServiceError(
                f'Failed to create user: {e.response.text}'
            )

    async def _assign_role_to_user(
        self,
        client: httpx.AsyncClient,
        realm_name: str,
        user_id: str,
        role_name: str,
    ) -> None:
        """Assign a realm role to a user."""
        # First, get the role representation
        role_url = (
            f'{self.keycloak_url}/admin/realms/{realm_name}/roles/{role_name}'
        )

        try:
            role_response = await client.get(
                role_url,
                headers=self._get_auth_headers(),
                timeout=30.0,
            )
            role_response.raise_for_status()
            role = role_response.json()

            # Assign role to user
            user_roles_url = f'{self.keycloak_url}/admin/realms/{realm_name}/users/{user_id}/role-mappings/realm'

            response = await client.post(
                user_roles_url,
                json=[role],
                headers=self._get_auth_headers(),
                timeout=30.0,
            )
            response.raise_for_status()
            logger.info(f'Assigned role {role_name} to user {user_id}')

        except httpx.HTTPStatusError as e:
            logger.error(f'Failed to assign role: {e.response.text}')
            raise KeycloakTenantServiceError(
                f'Failed to assign role: {e.response.text}'
            )

    async def assign_admin_role(
        self,
        realm_name: str,
        email: str,
    ) -> bool:
        """
        Assign admin role to a user by email.

        Args:
            realm_name: The Keycloak realm
            email: User's email address

        Returns:
            True if role assigned successfully
        """
        await self._get_admin_token()

        async with httpx.AsyncClient() as client:
            # Find user by email
            users_url = f'{self.keycloak_url}/admin/realms/{realm_name}/users'

            try:
                response = await client.get(
                    users_url,
                    params={'email': email},
                    headers=self._get_auth_headers(),
                    timeout=30.0,
                )
                response.raise_for_status()
                users = response.json()

                if not users:
                    logger.error(
                        f'User not found: {email} in realm {realm_name}'
                    )
                    return False

                user_id = users[0]['id']

                # Ensure admin role exists
                await self._create_role(
                    client, realm_name, 'admin', 'Administrator role'
                )

                # Assign admin role
                await self._assign_role_to_user(
                    client, realm_name, user_id, 'admin'
                )

                logger.info(
                    f'Assigned admin role to {email} in realm {realm_name}'
                )
                return True

            except httpx.HTTPStatusError as e:
                logger.error(f'Failed to assign admin role: {e.response.text}')
                return False
            except Exception as e:
                logger.error(f'Error assigning admin role: {e}')
                return False

    async def delete_tenant(self, realm_name: str) -> bool:
        """
        Delete a tenant (realm) from Keycloak.

        Args:
            realm_name: The realm name to delete

        Returns:
            True if successfully deleted
        """
        await self._get_admin_token()

        realm_url = f'{self.keycloak_url}/admin/realms/{realm_name}'

        async with httpx.AsyncClient() as client:
            try:
                response = await client.delete(
                    realm_url,
                    headers=self._get_auth_headers(),
                    timeout=30.0,
                )

                if response.status_code == 404:
                    raise TenantNotFoundError(f'Realm {realm_name} not found')

                response.raise_for_status()
                logger.info(f'Deleted tenant realm: {realm_name}')
                return True

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    raise TenantNotFoundError(f'Realm {realm_name} not found')
                logger.error(f'Failed to delete realm: {e.response.text}')
                raise KeycloakTenantServiceError(
                    f'Failed to delete realm: {e.response.text}'
                )

    async def get_tenant_clients(self, realm_name: str) -> List[Dict[str, Any]]:
        """
        Get all clients for a tenant realm.

        Args:
            realm_name: The realm name to fetch clients for

        Returns:
            List of client details
        """
        await self._get_admin_token()

        clients_url = f'{self.keycloak_url}/admin/realms/{realm_name}/clients'

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    clients_url,
                    headers=self._get_auth_headers(),
                    timeout=30.0,
                )

                if response.status_code == 404:
                    raise TenantNotFoundError(f'Realm {realm_name} not found')

                response.raise_for_status()
                clients = response.json()

                # Filter out built-in Keycloak clients and format response
                custom_clients = []
                builtin_clients = {
                    'account',
                    'account-console',
                    'admin-cli',
                    'broker',
                    'realm-management',
                    'security-admin-console',
                }

                for c in clients:
                    client_id = c.get('clientId', '')
                    if client_id not in builtin_clients:
                        client_info = {
                            'id': c.get('id'),
                            'clientId': client_id,
                            'name': c.get('name'),
                            'enabled': c.get('enabled'),
                            'publicClient': c.get('publicClient'),
                            'standardFlowEnabled': c.get('standardFlowEnabled'),
                            'directAccessGrantsEnabled': c.get(
                                'directAccessGrantsEnabled'
                            ),
                            'serviceAccountsEnabled': c.get(
                                'serviceAccountsEnabled'
                            ),
                            'redirectUris': c.get('redirectUris', []),
                            'webOrigins': c.get('webOrigins', []),
                        }

                        # Get client secret for confidential clients
                        if not c.get('publicClient'):
                            secret = await self._get_client_secret(
                                client, realm_name, c.get('id')
                            )
                            client_info['secret'] = secret

                        custom_clients.append(client_info)

                logger.info(
                    f'Retrieved {len(custom_clients)} clients for realm {realm_name}'
                )
                return custom_clients

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    raise TenantNotFoundError(f'Realm {realm_name} not found')
                logger.error(f'Failed to get clients: {e.response.text}')
                raise KeycloakTenantServiceError(
                    f'Failed to get clients: {e.response.text}'
                )

    async def _get_client_secret(
        self, client: httpx.AsyncClient, realm_name: str, client_uuid: str
    ) -> Optional[str]:
        """Get the secret for a confidential client."""
        secret_url = f'{self.keycloak_url}/admin/realms/{realm_name}/clients/{client_uuid}/client-secret'

        try:
            response = await client.get(
                secret_url,
                headers=self._get_auth_headers(),
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            return data.get('value')
        except httpx.HTTPStatusError:
            return None

    async def tenant_exists(self, realm_name: str) -> bool:
        """
        Check if a tenant realm exists.

        Args:
            realm_name: The realm name to check

        Returns:
            True if realm exists
        """
        await self._get_admin_token()

        realm_url = f'{self.keycloak_url}/admin/realms/{realm_name}'

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    realm_url,
                    headers=self._get_auth_headers(),
                    timeout=30.0,
                )
                return response.status_code == 200
            except httpx.HTTPError:
                return False

    async def list_tenants(self) -> List[Dict[str, Any]]:
        """
        List all tenant realms (excluding master and default realms).

        Returns:
            List of realm information
        """
        await self._get_admin_token()

        realms_url = f'{self.keycloak_url}/admin/realms'

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    realms_url,
                    headers=self._get_auth_headers(),
                    timeout=30.0,
                )
                response.raise_for_status()
                realms = response.json()

                # Filter to only codetether.run realms
                tenant_realms = []
                for realm in realms:
                    realm_name = realm.get('realm', '')
                    if realm_name.endswith('.codetether.run'):
                        tenant_realms.append(
                            {
                                'realm_name': realm_name,
                                'org_slug': realm_name.replace(
                                    '.codetether.run', ''
                                ),
                                'display_name': realm.get('displayName'),
                                'enabled': realm.get('enabled'),
                            }
                        )

                return tenant_realms

            except httpx.HTTPStatusError as e:
                logger.error(f'Failed to list realms: {e.response.text}')
                raise KeycloakTenantServiceError(
                    f'Failed to list realms: {e.response.text}'
                )


# Global tenant service instance
keycloak_tenant_service = KeycloakTenantService()
