"""
X (Twitter) Ads Campaign Management API Client.

Provides campaign management functionality for X advertising platform.
Implements the X Ads API v12 for managing ad accounts and campaigns.

References:
- https://developer.x.com/en/docs/x-ads-api/campaign-management/api-reference/accounts
- https://developer.x.com/en/docs/x-ads-api/campaign-management/api-reference/campaigns
"""

import base64
import hashlib
import hmac
import secrets
import time
from datetime import datetime
from enum import Enum
from typing import Any, Literal
from urllib.parse import quote

import httpx
from pydantic import BaseModel, Field


class XCampaignStatus(str, Enum):
    """Campaign entity status."""

    ACTIVE = 'ACTIVE'
    PAUSED = 'PAUSED'
    DRAFT = 'DRAFT'


class XCampaignObjective(str, Enum):
    """Campaign objective types."""

    REACH = 'REACH'
    ENGAGEMENT = 'ENGAGEMENT'
    VIDEO_VIEWS = 'VIDEO_VIEWS'
    WEBSITE_CLICKS = 'WEBSITE_CLICKS'
    APP_INSTALLS = 'APP_INSTALLS'
    FOLLOWERS = 'FOLLOWERS'


class XBudgetOptimization(str, Enum):
    """Budget optimization type."""

    CAMPAIGN = 'CAMPAIGN'
    LINE_ITEM = 'LINE_ITEM'


class XApprovalStatus(str, Enum):
    """Account approval status."""

    ACCEPTED = 'ACCEPTED'
    PENDING = 'PENDING'
    REJECTED = 'REJECTED'


class XAdAccount(BaseModel):
    """X Ads account model."""

    id: str = Field(description='Account identifier')
    name: str = Field(description='Account name')
    business_name: str | None = Field(None, description='Business name')
    timezone: str = Field(description='Account timezone')
    timezone_switch_at: datetime | None = Field(
        None, description='Timezone switch timestamp'
    )
    created_at: datetime = Field(description='Account creation timestamp')
    updated_at: datetime = Field(description='Last update timestamp')
    business_id: str | None = Field(None, description='Business ID')
    industry_type: str | None = Field(None, description='Industry type')
    approval_status: XApprovalStatus = Field(
        description='Account approval status'
    )
    deleted: bool = Field(
        default=False, description='Whether account is deleted'
    )


class XCampaign(BaseModel):
    """X Ads campaign model."""

    id: str = Field(description='Campaign identifier')
    name: str = Field(description='Campaign name')
    funding_instrument_id: str = Field(description='Funding instrument ID')
    daily_budget_amount_local_micro: int | None = Field(
        None,
        description='Daily budget in micro-currency units (e.g., $5.50 = 5500000)',
    )
    total_budget_amount_local_micro: int | None = Field(
        None, description='Total budget in micro-currency units'
    )
    entity_status: XCampaignStatus = Field(description='Campaign status')
    budget_optimization: XBudgetOptimization = Field(
        default=XBudgetOptimization.CAMPAIGN,
        description='Budget optimization type',
    )
    standard_delivery: bool = Field(
        default=True,
        description='Standard (True) or accelerated (False) delivery',
    )
    currency: str = Field(default='USD', description='Currency code')
    servable: bool | None = Field(
        None, description='Whether campaign is servable'
    )
    effective_status: str | None = Field(
        None, description='Effective campaign status'
    )
    reasons_not_servable: list[str] = Field(
        default_factory=list, description='Reasons why campaign is not servable'
    )
    purchase_order_number: str | None = Field(
        None, description='PO number for invoicing'
    )
    duration_in_days: int | None = Field(
        None, description='Campaign duration in days'
    )
    frequency_cap: int | None = Field(None, description='Frequency cap')
    created_at: datetime = Field(description='Creation timestamp')
    updated_at: datetime = Field(description='Last update timestamp')
    deleted: bool = Field(
        default=False, description='Whether campaign is deleted'
    )


class XCampaignCreate(BaseModel):
    """Request model for creating an X campaign."""

    name: str = Field(description='Campaign name (max 255 characters)')
    funding_instrument_id: str = Field(description='Funding instrument ID')
    daily_budget_amount_local_micro: int | None = Field(
        None,
        description='Daily budget in micro-currency (required for most funding instruments)',
    )
    total_budget_amount_local_micro: int | None = Field(
        None, description='Total budget in micro-currency'
    )
    entity_status: XCampaignStatus = Field(
        default=XCampaignStatus.PAUSED, description='Initial campaign status'
    )
    budget_optimization: XBudgetOptimization = Field(
        default=XBudgetOptimization.CAMPAIGN,
        description='Budget optimization type',
    )
    standard_delivery: bool = Field(
        default=True,
        description='Standard (True) or accelerated (False) delivery',
    )
    purchase_order_number: str | None = Field(
        None, description='PO number for invoicing (max 50 characters)'
    )


class XCampaignUpdate(BaseModel):
    """Request model for updating an X campaign."""

    name: str | None = Field(
        None, description='Campaign name (max 255 characters)'
    )
    daily_budget_amount_local_micro: int | None = Field(
        None, description='Daily budget in micro-currency'
    )
    total_budget_amount_local_micro: int | None = Field(
        None, description='Total budget in micro-currency'
    )
    entity_status: XCampaignStatus | None = Field(
        None, description='Campaign status (ACTIVE or PAUSED for updates)'
    )
    budget_optimization: XBudgetOptimization | None = Field(
        None, description='Budget optimization type'
    )
    standard_delivery: bool | None = Field(
        None, description='Standard (True) or accelerated (False) delivery'
    )
    purchase_order_number: str | None = Field(
        None, description='PO number for invoicing (max 50 characters)'
    )


class XPaginatedResponse(BaseModel):
    """Paginated response wrapper."""

    data: list[Any] = Field(description='Response data')
    next_cursor: str | None = Field(None, description='Cursor for next page')
    total_count: int | None = Field(
        None, description='Total count if requested'
    )


class XCampaignClient:
    """
    Client for X Ads Campaign Management API.

    Example usage:
        client = XCampaignClient(
            consumer_key="...",
            consumer_secret="...",
            access_token="...",
            access_token_secret="..."
        )

        # List accounts
        accounts = await client.list_accounts()

        # List campaigns for an account
        campaigns = await client.list_campaigns(account_id="18ce54d4x5t")

        # Create a campaign
        campaign = await client.create_campaign(
            account_id="18ce54d4x5t",
            campaign=XCampaignCreate(
                name="My Campaign",
                funding_instrument_id="lygyi",
                daily_budget_amount_local_micro=10000000,
                entity_status=XCampaignStatus.PAUSED
            )
        )
    """

    BASE_URL = 'https://ads-api.x.com/12'

    def __init__(
        self,
        consumer_key: str,
        consumer_secret: str,
        access_token: str,
        access_token_secret: str,
        sandbox: bool = False,
    ):
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.access_token = access_token
        self.access_token_secret = access_token_secret

        if sandbox:
            self.BASE_URL = 'https://ads-api-sandbox.twitter.com/12'

    def _generate_oauth_signature(
        self, method: str, url: str, params: dict[str, str]
    ) -> str:
        """Generate OAuth 1.0a signature for X API."""
        # Sort and encode parameters
        sorted_params = sorted(params.items())
        param_string = '&'.join(
            f'{quote(k, safe="")}={quote(v, safe="")}' for k, v in sorted_params
        )

        # Create signature base string
        base_string = '&'.join(
            [method.upper(), quote(url, safe=''), quote(param_string, safe='')]
        )

        # Create signing key
        signing_key = f'{quote(self.consumer_secret, safe="")}&{quote(self.access_token_secret, safe="")}'

        # Generate HMAC-SHA1 signature
        signature = hmac.new(
            signing_key.encode(), base_string.encode(), hashlib.sha1
        ).digest()

        return base64.b64encode(signature).decode()

    def _build_auth_header(self, method: str, url: str) -> str:
        """Build OAuth 1.0a Authorization header."""
        oauth_params = {
            'oauth_consumer_key': self.consumer_key,
            'oauth_nonce': secrets.token_hex(16),
            'oauth_signature_method': 'HMAC-SHA1',
            'oauth_timestamp': str(int(time.time())),
            'oauth_token': self.access_token,
            'oauth_version': '1.0',
        }

        # Generate signature
        signature = self._generate_oauth_signature(method, url, oauth_params)
        oauth_params['oauth_signature'] = signature

        # Build header
        header_parts = [
            f'{k}="{quote(v, safe="")}"'
            for k, v in sorted(oauth_params.items())
        ]
        return 'OAuth ' + ', '.join(header_parts)

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an authenticated request to the X Ads API."""
        url = f'{self.BASE_URL}{endpoint}'

        # Build URL with query params for GET/DELETE
        if params and method in ('GET', 'DELETE'):
            query_parts = []
            for k, v in params.items():
                if v is not None:
                    if isinstance(v, bool):
                        query_parts.append(f'{k}={str(v).lower()}')
                    elif isinstance(v, list):
                        query_parts.append(f'{k}={",".join(str(i) for i in v)}')
                    else:
                        query_parts.append(f'{k}={v}')
            if query_parts:
                url = f'{url}?{"&".join(query_parts)}'

        # For POST/PUT, params go in query string too (X API convention)
        if params and method in ('POST', 'PUT'):
            query_parts = []
            for k, v in params.items():
                if v is not None:
                    if isinstance(v, bool):
                        query_parts.append(f'{k}={str(v).lower()}')
                    elif isinstance(v, Enum):
                        query_parts.append(f'{k}={v.value}')
                    else:
                        query_parts.append(f'{k}={v}')
            if query_parts:
                url = f'{url}?{"&".join(query_parts)}'

        # Generate auth header using base URL (without query params for signature)
        base_url = url.split('?')[0]
        auth_header = self._build_auth_header(method, base_url)

        headers = {
            'Authorization': auth_header,
            'Content-Type': 'application/json',
        }

        async with httpx.AsyncClient() as client:
            if method == 'GET':
                response = await client.get(url, headers=headers, timeout=30.0)
            elif method == 'POST':
                response = await client.post(
                    url, headers=headers, json=json_body, timeout=30.0
                )
            elif method == 'PUT':
                response = await client.put(
                    url, headers=headers, json=json_body, timeout=30.0
                )
            elif method == 'DELETE':
                response = await client.delete(
                    url, headers=headers, timeout=30.0
                )
            else:
                raise ValueError(f'Unsupported HTTP method: {method}')

            response.raise_for_status()
            return response.json()

    # Account endpoints

    async def list_accounts(
        self,
        account_ids: list[str] | None = None,
        q: str | None = None,
        count: int = 200,
        cursor: str | None = None,
        with_deleted: bool = False,
        with_total_count: bool = False,
        sort_by: str | None = None,
    ) -> tuple[list[XAdAccount], str | None]:
        """
        List ad accounts the authenticated user has access to.

        Args:
            account_ids: Filter to specific account IDs
            q: Search query for account name (prefix match)
            count: Number of records (1-1000, default 200)
            cursor: Pagination cursor
            with_deleted: Include deleted accounts
            with_total_count: Include total count (exclusive with cursor)
            sort_by: Sort field and order (e.g., "created_at-asc")

        Returns:
            Tuple of (list of accounts, next cursor)
        """
        params: dict[str, Any] = {
            'count': count,
            'with_deleted': with_deleted,
        }

        if account_ids:
            params['account_ids'] = account_ids
        if q:
            params['q'] = q
        if cursor:
            params['cursor'] = cursor
        if with_total_count:
            params['with_total_count'] = with_total_count
        if sort_by:
            params['sort_by'] = sort_by

        response = await self._request('GET', '/accounts', params=params)

        accounts = [XAdAccount(**item) for item in response.get('data', [])]
        next_cursor = response.get('next_cursor')

        return accounts, next_cursor

    async def get_account(
        self, account_id: str, with_deleted: bool = False
    ) -> XAdAccount:
        """
        Get a specific ad account.

        Args:
            account_id: Account identifier
            with_deleted: Include if account is deleted

        Returns:
            The ad account
        """
        params = {'with_deleted': with_deleted}
        response = await self._request(
            'GET', f'/accounts/{account_id}', params=params
        )
        return XAdAccount(**response['data'])

    # Campaign endpoints

    async def list_campaigns(
        self,
        account_id: str,
        campaign_ids: list[str] | None = None,
        funding_instrument_ids: list[str] | None = None,
        q: str | None = None,
        count: int = 200,
        cursor: str | None = None,
        with_deleted: bool = False,
        with_draft: bool = False,
        with_total_count: bool = False,
        sort_by: str | None = None,
    ) -> tuple[list[XCampaign], str | None]:
        """
        List campaigns for an ad account.

        Args:
            account_id: Account identifier
            campaign_ids: Filter to specific campaign IDs (up to 200)
            funding_instrument_ids: Filter by funding instruments (up to 200)
            q: Search query for campaign name
            count: Number of records (1-1000, default 200)
            cursor: Pagination cursor
            with_deleted: Include deleted campaigns
            with_draft: Include draft campaigns
            with_total_count: Include total count (exclusive with cursor)
            sort_by: Sort field and order (e.g., "created_at-asc")

        Returns:
            Tuple of (list of campaigns, next cursor)
        """
        params: dict[str, Any] = {
            'count': count,
            'with_deleted': with_deleted,
            'with_draft': with_draft,
        }

        if campaign_ids:
            params['campaign_ids'] = campaign_ids
        if funding_instrument_ids:
            params['funding_instrument_ids'] = funding_instrument_ids
        if q:
            params['q'] = q
        if cursor:
            params['cursor'] = cursor
        if with_total_count:
            params['with_total_count'] = with_total_count
        if sort_by:
            params['sort_by'] = sort_by

        response = await self._request(
            'GET', f'/accounts/{account_id}/campaigns', params=params
        )

        campaigns = [XCampaign(**item) for item in response.get('data', [])]
        next_cursor = response.get('next_cursor')

        return campaigns, next_cursor

    async def get_campaign(
        self, account_id: str, campaign_id: str, with_deleted: bool = False
    ) -> XCampaign:
        """
        Get a specific campaign.

        Args:
            account_id: Account identifier
            campaign_id: Campaign identifier
            with_deleted: Include if campaign is deleted

        Returns:
            The campaign
        """
        params = {'with_deleted': with_deleted}
        response = await self._request(
            'GET',
            f'/accounts/{account_id}/campaigns/{campaign_id}',
            params=params,
        )
        return XCampaign(**response['data'])

    async def create_campaign(
        self, account_id: str, campaign: XCampaignCreate
    ) -> XCampaign:
        """
        Create a new campaign.

        Args:
            account_id: Account identifier
            campaign: Campaign creation parameters

        Returns:
            The created campaign
        """
        params: dict[str, Any] = {
            'name': campaign.name,
            'funding_instrument_id': campaign.funding_instrument_id,
            'entity_status': campaign.entity_status.value,
            'budget_optimization': campaign.budget_optimization.value,
            'standard_delivery': campaign.standard_delivery,
        }

        if campaign.daily_budget_amount_local_micro is not None:
            params['daily_budget_amount_local_micro'] = (
                campaign.daily_budget_amount_local_micro
            )
        if campaign.total_budget_amount_local_micro is not None:
            params['total_budget_amount_local_micro'] = (
                campaign.total_budget_amount_local_micro
            )
        if campaign.purchase_order_number:
            params['purchase_order_number'] = campaign.purchase_order_number

        response = await self._request(
            'POST', f'/accounts/{account_id}/campaigns', params=params
        )
        return XCampaign(**response['data'])

    async def update_campaign(
        self, account_id: str, campaign_id: str, updates: XCampaignUpdate
    ) -> XCampaign:
        """
        Update a campaign.

        Args:
            account_id: Account identifier
            campaign_id: Campaign identifier
            updates: Fields to update

        Returns:
            The updated campaign
        """
        params: dict[str, Any] = {}

        if updates.name is not None:
            params['name'] = updates.name
        if updates.daily_budget_amount_local_micro is not None:
            params['daily_budget_amount_local_micro'] = (
                updates.daily_budget_amount_local_micro
            )
        if updates.total_budget_amount_local_micro is not None:
            params['total_budget_amount_local_micro'] = (
                updates.total_budget_amount_local_micro
            )
        if updates.entity_status is not None:
            params['entity_status'] = updates.entity_status.value
        if updates.budget_optimization is not None:
            params['budget_optimization'] = updates.budget_optimization.value
        if updates.standard_delivery is not None:
            params['standard_delivery'] = updates.standard_delivery
        if updates.purchase_order_number is not None:
            params['purchase_order_number'] = updates.purchase_order_number

        response = await self._request(
            'PUT',
            f'/accounts/{account_id}/campaigns/{campaign_id}',
            params=params,
        )
        return XCampaign(**response['data'])

    async def delete_campaign(
        self, account_id: str, campaign_id: str
    ) -> XCampaign:
        """
        Delete a campaign.

        Note: This is not reversible. Subsequent delete attempts will return 404.

        Args:
            account_id: Account identifier
            campaign_id: Campaign identifier

        Returns:
            The deleted campaign (with deleted=True)
        """
        response = await self._request(
            'DELETE', f'/accounts/{account_id}/campaigns/{campaign_id}'
        )
        return XCampaign(**response['data'])

    # Batch operations

    async def batch_create_campaigns(
        self, account_id: str, campaigns: list[XCampaignCreate]
    ) -> list[XCampaign]:
        """
        Create multiple campaigns in a single batch request.

        Args:
            account_id: Account identifier
            campaigns: List of campaign creation parameters (max 40)

        Returns:
            List of created campaigns
        """
        if len(campaigns) > 40:
            raise ValueError('Maximum batch size is 40 campaigns')

        batch_payload = []
        for campaign in campaigns:
            params: dict[str, Any] = {
                'name': campaign.name,
                'funding_instrument_id': campaign.funding_instrument_id,
                'entity_status': campaign.entity_status.value,
                'budget_optimization': campaign.budget_optimization.value,
            }

            if campaign.daily_budget_amount_local_micro is not None:
                params['daily_budget_amount_local_micro'] = (
                    campaign.daily_budget_amount_local_micro
                )
            if campaign.total_budget_amount_local_micro is not None:
                params['total_budget_amount_local_micro'] = (
                    campaign.total_budget_amount_local_micro
                )
            if campaign.standard_delivery is not None:
                params['standard_delivery'] = campaign.standard_delivery
            if campaign.purchase_order_number:
                params['purchase_order_number'] = campaign.purchase_order_number

            batch_payload.append({'operation_type': 'Create', 'params': params})

        response = await self._request(
            'POST',
            f'/batch/accounts/{account_id}/campaigns',
            json_body=batch_payload,
        )

        return [XCampaign(**item) for item in response.get('data', [])]

    async def batch_update_campaigns(
        self, account_id: str, updates: list[tuple[str, XCampaignUpdate]]
    ) -> list[XCampaign]:
        """
        Update multiple campaigns in a single batch request.

        Args:
            account_id: Account identifier
            updates: List of (campaign_id, updates) tuples (max 40)

        Returns:
            List of updated campaigns
        """
        if len(updates) > 40:
            raise ValueError('Maximum batch size is 40 campaigns')

        batch_payload = []
        for campaign_id, update in updates:
            params: dict[str, Any] = {'campaign_id': campaign_id}

            if update.name is not None:
                params['name'] = update.name
            if update.daily_budget_amount_local_micro is not None:
                params['daily_budget_amount_local_micro'] = (
                    update.daily_budget_amount_local_micro
                )
            if update.total_budget_amount_local_micro is not None:
                params['total_budget_amount_local_micro'] = (
                    update.total_budget_amount_local_micro
                )
            if update.entity_status is not None:
                params['entity_status'] = update.entity_status.value
            if update.budget_optimization is not None:
                params['budget_optimization'] = update.budget_optimization.value
            if update.standard_delivery is not None:
                params['standard_delivery'] = update.standard_delivery
            if update.purchase_order_number is not None:
                params['purchase_order_number'] = update.purchase_order_number

            batch_payload.append({'operation_type': 'Update', 'params': params})

        response = await self._request(
            'POST',
            f'/batch/accounts/{account_id}/campaigns',
            json_body=batch_payload,
        )

        return [XCampaign(**item) for item in response.get('data', [])]


# Helper functions for common operations


def dollars_to_micro(dollars: float) -> int:
    """Convert dollars to micro-currency units."""
    return int(dollars * 1_000_000)


def micro_to_dollars(micro: int) -> float:
    """Convert micro-currency units to dollars."""
    return micro / 1_000_000


async def get_x_campaign_client(
    consumer_key: str | None = None,
    consumer_secret: str | None = None,
    access_token: str | None = None,
    access_token_secret: str | None = None,
    sandbox: bool = False,
) -> XCampaignClient:
    """
    Create an XCampaignClient with credentials from parameters or environment.

    If credentials not provided, reads from environment:
    - X_ADS_CONSUMER_KEY
    - X_ADS_CONSUMER_SECRET
    - X_ADS_ACCESS_TOKEN
    - X_ADS_ACCESS_TOKEN_SECRET
    """
    import os

    return XCampaignClient(
        consumer_key=consumer_key or os.environ['X_ADS_CONSUMER_KEY'],
        consumer_secret=consumer_secret or os.environ['X_ADS_CONSUMER_SECRET'],
        access_token=access_token or os.environ['X_ADS_ACCESS_TOKEN'],
        access_token_secret=access_token_secret
        or os.environ['X_ADS_ACCESS_TOKEN_SECRET'],
        sandbox=sandbox,
    )
