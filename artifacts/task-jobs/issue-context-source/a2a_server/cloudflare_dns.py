"""
Cloudflare DNS and Tunnel Management for Tenant Provisioning.

This module handles automatic DNS record creation and Cloudflare Tunnel
configuration when provisioning new tenant instances.

For each tenant subdomain (e.g., riley-041b27.codetether.run):
1. Creates a CNAME DNS record pointing to the base domain
2. Adds an ingress rule to the Cloudflare Tunnel configuration
"""

import logging
import os
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

import httpx

logger = logging.getLogger(__name__)

# Configuration from environment
CLOUDFLARE_API_TOKEN = os.environ.get('CLOUDFLARE_API_TOKEN')
CLOUDFLARE_ZONE_ID = os.environ.get(
    'CLOUDFLARE_ZONE_ID', '5059c11395b9eb527438be98150fc321'
)
CLOUDFLARE_ACCOUNT_ID = os.environ.get(
    'CLOUDFLARE_ACCOUNT_ID', 'b10de17b4e643f04b9aab51db72e5376'
)
CLOUDFLARE_TUNNEL_ID = os.environ.get(
    'CLOUDFLARE_TUNNEL_ID', 'dc7f7221-95ad-4cfb-b679-b3473cef4f1c'
)
BASE_DOMAIN = os.environ.get('CODETETHER_BASE_DOMAIN', 'codetether.run')

# Ingress controller service for tunnel routing
INGRESS_SERVICE = (
    'https://ingress-nginx-controller.ingress-nginx.svc.cluster.local:443'
)


@dataclass
class CloudflareDNSResult:
    """Result of DNS/Tunnel operation."""

    success: bool
    dns_record_id: Optional[str] = None
    error_message: Optional[str] = None


class CloudflareDNSService:
    """
    Service for managing Cloudflare DNS records and Tunnel configuration.

    Handles automatic subdomain setup for tenant provisioning.
    """

    def __init__(self, api_token: Optional[str] = None):
        self.api_token = api_token or CLOUDFLARE_API_TOKEN
        self.base_url = 'https://api.cloudflare.com/client/v4'
        self.zone_id = CLOUDFLARE_ZONE_ID
        self.account_id = CLOUDFLARE_ACCOUNT_ID
        self.tunnel_id = CLOUDFLARE_TUNNEL_ID

    def _get_headers(self) -> Dict[str, str]:
        """Get authorization headers."""
        return {
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json',
        }

    async def setup_tenant_subdomain(
        self,
        subdomain: str,
        tenant_id: str,
    ) -> CloudflareDNSResult:
        """
        Set up DNS and tunnel routing for a tenant subdomain.

        Args:
            subdomain: The subdomain part (e.g., 'riley-041b27')
            tenant_id: The tenant's ID for tagging

        Returns:
            CloudflareDNSResult with operation status
        """
        if not self.api_token:
            logger.warning(
                'Cloudflare API token not configured, skipping DNS setup'
            )
            return CloudflareDNSResult(
                success=False,
                error_message='Cloudflare API token not configured',
            )

        hostname = f'{subdomain}.{BASE_DOMAIN}'
        logger.info(f'Setting up DNS for tenant {tenant_id}: {hostname}')

        try:
            # Step 1: Create CNAME DNS record
            dns_result = await self._create_cname_record(
                subdomain=subdomain,
                target=BASE_DOMAIN,
                comment=f'Tenant: {tenant_id}',
            )

            if not dns_result.success:
                return dns_result

            # Step 2: Add tunnel ingress rule
            tunnel_result = await self._add_tunnel_ingress(hostname)

            if not tunnel_result:
                logger.warning(
                    f'DNS created but tunnel config failed for {hostname}'
                )
                # DNS was created, so partial success
                return CloudflareDNSResult(
                    success=True,
                    dns_record_id=dns_result.dns_record_id,
                    error_message='DNS created but tunnel config may need manual update',
                )

            logger.info(f'Successfully set up DNS and tunnel for {hostname}')
            return CloudflareDNSResult(
                success=True,
                dns_record_id=dns_result.dns_record_id,
            )

        except Exception as e:
            logger.error(f'Failed to set up DNS for {hostname}: {e}')
            return CloudflareDNSResult(
                success=False,
                error_message=str(e),
            )

    async def _create_cname_record(
        self,
        subdomain: str,
        target: str,
        comment: str = '',
    ) -> CloudflareDNSResult:
        """Create a CNAME DNS record."""
        url = f'{self.base_url}/zones/{self.zone_id}/dns_records'

        payload = {
            'type': 'CNAME',
            'name': subdomain,
            'content': target,
            'proxied': True,  # Enable Cloudflare proxy for SSL/security
            'comment': comment,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=self._get_headers(),
                json=payload,
            )

            data = response.json()

            if response.status_code == 200 and data.get('success'):
                record_id = data['result']['id']
                logger.info(f'Created DNS record {subdomain} -> {target}')
                return CloudflareDNSResult(
                    success=True,
                    dns_record_id=record_id,
                )

            # Check if record already exists
            if response.status_code == 400:
                errors = data.get('errors', [])
                for error in errors:
                    if 'already exists' in error.get('message', '').lower():
                        logger.info(f'DNS record {subdomain} already exists')
                        # Try to get existing record ID
                        existing = await self._get_dns_record(subdomain)
                        return CloudflareDNSResult(
                            success=True,
                            dns_record_id=existing,
                        )

            error_msg = data.get('errors', [{'message': 'Unknown error'}])[
                0
            ].get('message')
            logger.error(f'Failed to create DNS record: {error_msg}')
            return CloudflareDNSResult(
                success=False,
                error_message=error_msg,
            )

    async def _get_dns_record(self, subdomain: str) -> Optional[str]:
        """Get existing DNS record ID."""
        url = f'{self.base_url}/zones/{self.zone_id}/dns_records'
        params = {
            'name': f'{subdomain}.{BASE_DOMAIN}',
            'type': 'CNAME',
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers=self._get_headers(),
                params=params,
            )

            data = response.json()
            if data.get('success') and data.get('result'):
                return data['result'][0]['id']

        return None

    async def _add_tunnel_ingress(self, hostname: str) -> bool:
        """Add ingress rule to Cloudflare Tunnel configuration."""
        # Get current config
        config_url = (
            f'{self.base_url}/accounts/{self.account_id}'
            f'/cfd_tunnel/{self.tunnel_id}/configurations'
        )

        async with httpx.AsyncClient() as client:
            # Get current configuration
            response = await client.get(
                config_url,
                headers=self._get_headers(),
            )

            if response.status_code != 200:
                logger.error(f'Failed to get tunnel config: {response.text}')
                return False

            data = response.json()
            if not data.get('success'):
                logger.error(f'Tunnel config error: {data}')
                return False

            current_config = data['result']['config']
            ingress_rules = current_config.get('ingress', [])

            # Check if hostname already exists
            for rule in ingress_rules:
                if rule.get('hostname') == hostname:
                    logger.info(f'Tunnel ingress for {hostname} already exists')
                    return True

            # Add new rule before the catch-all (last rule)
            new_rule = {
                'service': INGRESS_SERVICE,
                'hostname': hostname,
                'originRequest': {
                    'noTLSVerify': True,
                },
            }

            # Insert before the catch-all rule (http_status:404)
            if ingress_rules and 'hostname' not in ingress_rules[-1]:
                # Last rule is catch-all, insert before it
                ingress_rules.insert(-1, new_rule)
            else:
                ingress_rules.append(new_rule)

            # Update configuration
            new_config = {
                'config': {
                    'ingress': ingress_rules,
                    'warp-routing': current_config.get(
                        'warp-routing', {'enabled': False}
                    ),
                }
            }

            response = await client.put(
                config_url,
                headers=self._get_headers(),
                json=new_config,
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    logger.info(f'Added tunnel ingress for {hostname}')
                    return True

            logger.error(f'Failed to update tunnel config: {response.text}')
            return False

    async def delete_tenant_subdomain(
        self,
        subdomain: str,
    ) -> bool:
        """
        Remove DNS record and tunnel ingress for a tenant.

        Called when deprovisioning a tenant.
        """
        if not self.api_token:
            logger.warning('Cloudflare API token not configured')
            return False

        hostname = f'{subdomain}.{BASE_DOMAIN}'
        logger.info(f'Removing DNS for {hostname}')

        success = True

        # Delete DNS record
        record_id = await self._get_dns_record(subdomain)
        if record_id:
            url = (
                f'{self.base_url}/zones/{self.zone_id}/dns_records/{record_id}'
            )
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    url,
                    headers=self._get_headers(),
                )
                if response.status_code == 200:
                    logger.info(f'Deleted DNS record for {subdomain}')
                else:
                    logger.error(
                        f'Failed to delete DNS record: {response.text}'
                    )
                    success = False

        # Remove tunnel ingress
        tunnel_success = await self._remove_tunnel_ingress(hostname)
        if not tunnel_success:
            success = False

        return success

    async def _remove_tunnel_ingress(self, hostname: str) -> bool:
        """Remove ingress rule from Cloudflare Tunnel configuration."""
        config_url = (
            f'{self.base_url}/accounts/{self.account_id}'
            f'/cfd_tunnel/{self.tunnel_id}/configurations'
        )

        async with httpx.AsyncClient() as client:
            response = await client.get(
                config_url,
                headers=self._get_headers(),
            )

            if response.status_code != 200:
                return False

            data = response.json()
            current_config = data['result']['config']
            ingress_rules = current_config.get('ingress', [])

            # Filter out the hostname
            new_rules = [
                rule
                for rule in ingress_rules
                if rule.get('hostname') != hostname
            ]

            if len(new_rules) == len(ingress_rules):
                logger.info(f'Tunnel ingress for {hostname} not found')
                return True

            new_config = {
                'config': {
                    'ingress': new_rules,
                    'warp-routing': current_config.get(
                        'warp-routing', {'enabled': False}
                    ),
                }
            }

            response = await client.put(
                config_url,
                headers=self._get_headers(),
                json=new_config,
            )

            if response.status_code == 200:
                logger.info(f'Removed tunnel ingress for {hostname}')
                return True

            logger.error(f'Failed to remove tunnel ingress: {response.text}')
            return False


# Global service instance
cloudflare_dns_service = CloudflareDNSService()


async def setup_tenant_dns(
    subdomain: str, tenant_id: str
) -> CloudflareDNSResult:
    """Convenience function to set up DNS for a tenant."""
    return await cloudflare_dns_service.setup_tenant_subdomain(
        subdomain, tenant_id
    )


async def delete_tenant_dns(subdomain: str) -> bool:
    """Convenience function to delete DNS for a tenant."""
    return await cloudflare_dns_service.delete_tenant_subdomain(subdomain)
