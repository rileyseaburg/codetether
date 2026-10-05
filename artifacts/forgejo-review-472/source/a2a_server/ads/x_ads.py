"""
X (Twitter) Ads API Client - Line Items & Promoted Tweets.

Implements the X Ads API v12 for campaign management:
- Line Items (Ad Groups): targeting, bidding, and placement config
- Promoted Tweets (Ads): individual ad creatives

Uses OAuth 1.0a authentication (same pattern as x_conversions.py).

References:
- https://developer.x.com/en/docs/x-ads-api/campaign-management/api-reference/line-items
- https://developer.x.com/en/docs/x-ads-api/campaign-management/api-reference/promoted-tweets
"""

import base64
import hashlib
import hmac
import secrets
import time
from typing import Any, Literal
from urllib.parse import quote, urlencode

import httpx
from pydantic import BaseModel, Field


# =============================================================================
# Pydantic Models - Line Items
# =============================================================================


class XLineItem(BaseModel):
    """X Ads Line Item (Ad Group) response model."""

    id: str = Field(description='Line item ID')
    campaign_id: str = Field(description='Parent campaign ID')
    name: str = Field(description='Line item name')
    bid_amount_local_micro: int | None = Field(
        None, description='Bid amount in micros (1/1,000,000 of local currency)'
    )
    bid_type: str | None = Field(
        None, description='Bid type (e.g., AUTO, MAX, TARGET)'
    )
    product_type: str = Field(
        description='Product type (e.g., PROMOTED_TWEETS, PROMOTED_ACCOUNTS)'
    )
    placements: list[str] | None = Field(
        None,
        description='Ad placements (e.g., ALL_ON_TWITTER, TWITTER_TIMELINE)',
    )
    status: str = Field(description='Entity status (ACTIVE, PAUSED, DRAFT)')
    targeting_criteria: dict[str, Any] | None = Field(
        None, description='Targeting configuration'
    )
    # Additional common fields
    objective: str | None = Field(None, description='Campaign objective')
    start_time: str | None = Field(None, description='Start time (ISO 8601)')
    end_time: str | None = Field(None, description='End time (ISO 8601)')
    total_budget_amount_local_micro: int | None = Field(
        None, description='Total budget in micros'
    )
    daily_budget_amount_local_micro: int | None = Field(
        None, description='Daily budget in micros'
    )
    created_at: str | None = Field(None, description='Creation timestamp')
    updated_at: str | None = Field(None, description='Last update timestamp')


class XLineItemCreate(BaseModel):
    """Request model for creating a Line Item."""

    campaign_id: str = Field(description='Parent campaign ID')
    name: str = Field(description='Line item name')
    product_type: Literal[
        'PROMOTED_TWEETS',
        'PROMOTED_ACCOUNTS',
        'PROMOTED_TRENDS',
        'MEDIA_VIEW',
        'FOLLOWERS',
        'WEBSITE_CLICKS',
        'APP_INSTALLS',
        'APP_ENGAGEMENTS',
        'VIDEO_VIEWS',
        'PREROLL_VIEWS',
    ] = Field(description='Product type for the line item')
    placements: (
        list[
            Literal[
                'ALL_ON_TWITTER',
                'PUBLISHER_NETWORK',
                'TWITTER_PROFILE',
                'TWITTER_SEARCH',
                'TWITTER_TIMELINE',
            ]
        ]
        | None
    ) = Field(None, description='Ad placements')
    bid_amount_local_micro: int | None = Field(
        None, description='Bid amount in micros'
    )
    bid_type: Literal['AUTO', 'MAX', 'TARGET'] | None = Field(
        None, description='Bid type'
    )
    objective: (
        Literal[
            'APP_ENGAGEMENTS',
            'APP_INSTALLS',
            'AWARENESS',
            'ENGAGEMENTS',
            'FOLLOWERS',
            'PREROLL_VIEWS',
            'REACH',
            'VIDEO_VIEWS',
            'WEBSITE_CLICKS',
            'WEBSITE_CONVERSIONS',
        ]
        | None
    ) = Field(None, description='Campaign objective')
    start_time: str | None = Field(None, description='Start time (ISO 8601)')
    end_time: str | None = Field(None, description='End time (ISO 8601)')
    total_budget_amount_local_micro: int | None = Field(
        None, description='Total budget in micros'
    )
    daily_budget_amount_local_micro: int | None = Field(
        None, description='Daily budget in micros'
    )
    entity_status: Literal['ACTIVE', 'PAUSED', 'DRAFT'] = Field(
        'PAUSED', description='Initial status'
    )
    automatically_select_bid: bool | None = Field(
        None, description='Let X automatically select bid'
    )


class XLineItemUpdate(BaseModel):
    """Request model for updating a Line Item."""

    name: str | None = Field(None, description='Line item name')
    bid_amount_local_micro: int | None = Field(
        None, description='Bid amount in micros'
    )
    bid_type: Literal['AUTO', 'MAX', 'TARGET'] | None = Field(
        None, description='Bid type'
    )
    placements: list[str] | None = Field(None, description='Ad placements')
    start_time: str | None = Field(None, description='Start time (ISO 8601)')
    end_time: str | None = Field(None, description='End time (ISO 8601)')
    total_budget_amount_local_micro: int | None = Field(
        None, description='Total budget in micros'
    )
    daily_budget_amount_local_micro: int | None = Field(
        None, description='Daily budget in micros'
    )
    entity_status: Literal['ACTIVE', 'PAUSED', 'DRAFT'] | None = Field(
        None, description='Entity status'
    )
    automatically_select_bid: bool | None = Field(
        None, description='Let X automatically select bid'
    )


# =============================================================================
# Pydantic Models - Promoted Tweets
# =============================================================================


class XPromotedTweet(BaseModel):
    """X Ads Promoted Tweet (Ad) response model."""

    id: str = Field(description='Promoted tweet ID')
    line_item_id: str = Field(description='Parent line item ID')
    tweet_id: str = Field(description='Source tweet ID')
    status: str = Field(description='Approval/entity status')
    # Additional common fields
    approval_status: str | None = Field(
        None, description='Ad approval status (ACCEPTED, PENDING, etc.)'
    )
    created_at: str | None = Field(None, description='Creation timestamp')
    updated_at: str | None = Field(None, description='Last update timestamp')
    deleted: bool | None = Field(None, description='Deletion flag')


class XPromotedTweetCreate(BaseModel):
    """Request model for creating a Promoted Tweet."""

    line_item_id: str = Field(description='Parent line item ID')
    tweet_id: str = Field(description='Tweet ID to promote')


# =============================================================================
# X Ads API Client
# =============================================================================


class XAdsClient:
    """
    Client for X Ads API - Line Items & Promoted Tweets.

    Example usage:
        client = XAdsClient(
            consumer_key="...",
            consumer_secret="...",
            access_token="...",
            access_token_secret="..."
        )

        # List line items
        line_items = await client.list_line_items(account_id="abc123")

        # Create a line item
        line_item = await client.create_line_item(
            account_id="abc123",
            data=XLineItemCreate(
                campaign_id="camp123",
                name="My Line Item",
                product_type="PROMOTED_TWEETS"
            )
        )

        # Create a promoted tweet
        promoted = await client.create_promoted_tweet(
            account_id="abc123",
            data=XPromotedTweetCreate(
                line_item_id="li123",
                tweet_id="tweet456"
            )
        )
    """

    BASE_URL = 'https://ads-api.twitter.com/12'

    def __init__(
        self,
        consumer_key: str,
        consumer_secret: str,
        access_token: str,
        access_token_secret: str,
        timeout: float = 30.0,
    ):
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.access_token = access_token
        self.access_token_secret = access_token_secret
        self.timeout = timeout

    # -------------------------------------------------------------------------
    # OAuth 1.0a Authentication
    # -------------------------------------------------------------------------

    def _generate_oauth_signature(
        self, method: str, url: str, params: dict[str, str]
    ) -> str:
        """Generate OAuth 1.0a HMAC-SHA1 signature."""
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
        signing_key = (
            f'{quote(self.consumer_secret, safe="")}&'
            f'{quote(self.access_token_secret, safe="")}'
        )

        # Generate HMAC-SHA1 signature
        signature = hmac.new(
            signing_key.encode(), base_string.encode(), hashlib.sha1
        ).digest()

        return base64.b64encode(signature).decode()

    def _build_auth_header(
        self, method: str, url: str, query_params: dict[str, str] | None = None
    ) -> str:
        """Build OAuth 1.0a Authorization header."""
        oauth_params = {
            'oauth_consumer_key': self.consumer_key,
            'oauth_nonce': secrets.token_hex(16),
            'oauth_signature_method': 'HMAC-SHA1',
            'oauth_timestamp': str(int(time.time())),
            'oauth_token': self.access_token,
            'oauth_version': '1.0',
        }

        # Combine OAuth params with query params for signature
        all_params = {**oauth_params}
        if query_params:
            all_params.update(query_params)

        # Generate signature using base URL (without query string)
        base_url = url.split('?')[0]
        signature = self._generate_oauth_signature(method, base_url, all_params)
        oauth_params['oauth_signature'] = signature

        # Build header
        header_parts = [
            f'{k}="{quote(v, safe="")}"'
            for k, v in sorted(oauth_params.items())
        ]
        return 'OAuth ' + ', '.join(header_parts)

    # -------------------------------------------------------------------------
    # HTTP Request Helpers
    # -------------------------------------------------------------------------

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an authenticated request to the X Ads API."""
        url = f'{self.BASE_URL}{endpoint}'

        # Filter out None values from params
        if params:
            params = {k: v for k, v in params.items() if v is not None}

        # Convert params to strings for OAuth signature
        str_params = {k: str(v) for k, v in (params or {}).items()}

        auth_header = self._build_auth_header(method, url, str_params)

        headers = {
            'Authorization': auth_header,
            'Content-Type': 'application/json',
        }

        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()

    # -------------------------------------------------------------------------
    # Line Items (Ad Groups) Endpoints
    # -------------------------------------------------------------------------

    async def list_line_items(
        self,
        account_id: str,
        campaign_ids: list[str] | None = None,
        line_item_ids: list[str] | None = None,
        funding_instrument_ids: list[str] | None = None,
        count: int = 200,
        cursor: str | None = None,
        sort_by: Literal['created_at', 'updated_at', 'name'] | None = None,
        with_deleted: bool = False,
        with_total_count: bool = False,
    ) -> dict[str, Any]:
        """
        List line items for an account.

        GET /accounts/{account_id}/line_items

        Args:
            account_id: The ads account ID
            campaign_ids: Filter by campaign IDs (comma-separated)
            line_item_ids: Filter by specific line item IDs
            funding_instrument_ids: Filter by funding instrument IDs
            count: Number of results (1-1000, default 200)
            cursor: Pagination cursor
            sort_by: Sort field
            with_deleted: Include deleted line items
            with_total_count: Include total count in response

        Returns:
            API response with line items data
        """
        params: dict[str, Any] = {
            'count': min(count, 1000),
            'with_deleted': str(with_deleted).lower(),
            'with_total_count': str(with_total_count).lower(),
        }

        if campaign_ids:
            params['campaign_ids'] = ','.join(campaign_ids)
        if line_item_ids:
            params['line_item_ids'] = ','.join(line_item_ids)
        if funding_instrument_ids:
            params['funding_instrument_ids'] = ','.join(funding_instrument_ids)
        if cursor:
            params['cursor'] = cursor
        if sort_by:
            params['sort_by'] = sort_by

        return await self._request(
            'GET', f'/accounts/{account_id}/line_items', params=params
        )

    async def get_line_item(
        self, account_id: str, line_item_id: str, with_deleted: bool = False
    ) -> dict[str, Any]:
        """
        Get a single line item by ID.

        GET /accounts/{account_id}/line_items/{line_item_id}
        """
        params = {'with_deleted': str(with_deleted).lower()}
        return await self._request(
            'GET',
            f'/accounts/{account_id}/line_items/{line_item_id}',
            params=params,
        )

    async def create_line_item(
        self, account_id: str, data: XLineItemCreate
    ) -> dict[str, Any]:
        """
        Create a new line item.

        POST /accounts/{account_id}/line_items

        Args:
            account_id: The ads account ID
            data: Line item creation data

        Returns:
            API response with created line item
        """
        # Convert Pydantic model to dict, excluding None values
        payload = data.model_dump(exclude_none=True)

        # Convert placements list to comma-separated string if present
        if 'placements' in payload and isinstance(payload['placements'], list):
            payload['placements'] = ','.join(payload['placements'])

        return await self._request(
            'POST',
            f'/accounts/{account_id}/line_items',
            params=payload,  # X Ads API uses form params for POST
        )

    async def update_line_item(
        self, account_id: str, line_item_id: str, data: XLineItemUpdate
    ) -> dict[str, Any]:
        """
        Update an existing line item.

        PUT /accounts/{account_id}/line_items/{line_item_id}

        Args:
            account_id: The ads account ID
            line_item_id: The line item ID to update
            data: Line item update data

        Returns:
            API response with updated line item
        """
        payload = data.model_dump(exclude_none=True)

        # Convert placements list to comma-separated string if present
        if 'placements' in payload and isinstance(payload['placements'], list):
            payload['placements'] = ','.join(payload['placements'])

        return await self._request(
            'PUT',
            f'/accounts/{account_id}/line_items/{line_item_id}',
            params=payload,
        )

    async def delete_line_item(
        self, account_id: str, line_item_id: str
    ) -> dict[str, Any]:
        """
        Delete a line item.

        DELETE /accounts/{account_id}/line_items/{line_item_id}

        Note: This is a soft delete. The line item will be marked as deleted
        but can still be retrieved with with_deleted=True.
        """
        return await self._request(
            'DELETE', f'/accounts/{account_id}/line_items/{line_item_id}'
        )

    # -------------------------------------------------------------------------
    # Promoted Tweets (Ads) Endpoints
    # -------------------------------------------------------------------------

    async def list_promoted_tweets(
        self,
        account_id: str,
        line_item_ids: list[str] | None = None,
        promoted_tweet_ids: list[str] | None = None,
        count: int = 200,
        cursor: str | None = None,
        sort_by: Literal['created_at', 'updated_at'] | None = None,
        with_deleted: bool = False,
        with_total_count: bool = False,
    ) -> dict[str, Any]:
        """
        List promoted tweets for an account.

        GET /accounts/{account_id}/promoted_tweets

        Args:
            account_id: The ads account ID
            line_item_ids: Filter by line item IDs
            promoted_tweet_ids: Filter by specific promoted tweet IDs
            count: Number of results (1-1000, default 200)
            cursor: Pagination cursor
            sort_by: Sort field
            with_deleted: Include deleted promoted tweets
            with_total_count: Include total count in response

        Returns:
            API response with promoted tweets data
        """
        params: dict[str, Any] = {
            'count': min(count, 1000),
            'with_deleted': str(with_deleted).lower(),
            'with_total_count': str(with_total_count).lower(),
        }

        if line_item_ids:
            params['line_item_ids'] = ','.join(line_item_ids)
        if promoted_tweet_ids:
            params['promoted_tweet_ids'] = ','.join(promoted_tweet_ids)
        if cursor:
            params['cursor'] = cursor
        if sort_by:
            params['sort_by'] = sort_by

        return await self._request(
            'GET', f'/accounts/{account_id}/promoted_tweets', params=params
        )

    async def get_promoted_tweet(
        self,
        account_id: str,
        promoted_tweet_id: str,
        with_deleted: bool = False,
    ) -> dict[str, Any]:
        """
        Get a single promoted tweet by ID.

        GET /accounts/{account_id}/promoted_tweets/{promoted_tweet_id}
        """
        params = {'with_deleted': str(with_deleted).lower()}
        return await self._request(
            'GET',
            f'/accounts/{account_id}/promoted_tweets/{promoted_tweet_id}',
            params=params,
        )

    async def create_promoted_tweet(
        self, account_id: str, data: XPromotedTweetCreate
    ) -> dict[str, Any]:
        """
        Create a new promoted tweet.

        POST /accounts/{account_id}/promoted_tweets

        Args:
            account_id: The ads account ID
            data: Promoted tweet creation data

        Returns:
            API response with created promoted tweet
        """
        payload = data.model_dump(exclude_none=True)

        return await self._request(
            'POST', f'/accounts/{account_id}/promoted_tweets', params=payload
        )

    async def delete_promoted_tweet(
        self, account_id: str, promoted_tweet_id: str
    ) -> dict[str, Any]:
        """
        Delete a promoted tweet.

        DELETE /accounts/{account_id}/promoted_tweets/{promoted_tweet_id}

        Note: This is a soft delete. The promoted tweet will be marked as
        deleted but can still be retrieved with with_deleted=True.
        """
        return await self._request(
            'DELETE',
            f'/accounts/{account_id}/promoted_tweets/{promoted_tweet_id}',
        )

    # -------------------------------------------------------------------------
    # Convenience Methods
    # -------------------------------------------------------------------------

    async def get_all_line_items(
        self,
        account_id: str,
        campaign_ids: list[str] | None = None,
        with_deleted: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Fetch all line items with automatic pagination.

        Args:
            account_id: The ads account ID
            campaign_ids: Optional filter by campaign IDs
            with_deleted: Include deleted line items

        Returns:
            List of all line items
        """
        all_items: list[dict[str, Any]] = []
        cursor: str | None = None

        while True:
            response = await self.list_line_items(
                account_id=account_id,
                campaign_ids=campaign_ids,
                cursor=cursor,
                count=1000,
                with_deleted=with_deleted,
            )

            data = response.get('data', [])
            all_items.extend(data)

            # Check for next cursor
            next_cursor = response.get('next_cursor')
            if not next_cursor or not data:
                break
            cursor = next_cursor

        return all_items

    async def get_all_promoted_tweets(
        self,
        account_id: str,
        line_item_ids: list[str] | None = None,
        with_deleted: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Fetch all promoted tweets with automatic pagination.

        Args:
            account_id: The ads account ID
            line_item_ids: Optional filter by line item IDs
            with_deleted: Include deleted promoted tweets

        Returns:
            List of all promoted tweets
        """
        all_items: list[dict[str, Any]] = []
        cursor: str | None = None

        while True:
            response = await self.list_promoted_tweets(
                account_id=account_id,
                line_item_ids=line_item_ids,
                cursor=cursor,
                count=1000,
                with_deleted=with_deleted,
            )

            data = response.get('data', [])
            all_items.extend(data)

            # Check for next cursor
            next_cursor = response.get('next_cursor')
            if not next_cursor or not data:
                break
            cursor = next_cursor

        return all_items

    def parse_line_items(self, response: dict[str, Any]) -> list[XLineItem]:
        """Parse API response into XLineItem models."""
        data = response.get('data', [])
        return [
            XLineItem(
                id=item['id'],
                campaign_id=item.get('campaign_id', ''),
                name=item.get('name', ''),
                bid_amount_local_micro=item.get('bid_amount_local_micro'),
                bid_type=item.get('bid_type'),
                product_type=item.get('product_type', ''),
                placements=item.get('placements'),
                status=item.get('entity_status', 'UNKNOWN'),
                targeting_criteria=item.get('targeting_criteria'),
                objective=item.get('objective'),
                start_time=item.get('start_time'),
                end_time=item.get('end_time'),
                total_budget_amount_local_micro=item.get(
                    'total_budget_amount_local_micro'
                ),
                daily_budget_amount_local_micro=item.get(
                    'daily_budget_amount_local_micro'
                ),
                created_at=item.get('created_at'),
                updated_at=item.get('updated_at'),
            )
            for item in data
        ]

    def parse_promoted_tweets(
        self, response: dict[str, Any]
    ) -> list[XPromotedTweet]:
        """Parse API response into XPromotedTweet models."""
        data = response.get('data', [])
        return [
            XPromotedTweet(
                id=item['id'],
                line_item_id=item.get('line_item_id', ''),
                tweet_id=item.get('tweet_id', ''),
                status=item.get('entity_status', 'UNKNOWN'),
                approval_status=item.get('approval_status'),
                created_at=item.get('created_at'),
                updated_at=item.get('updated_at'),
                deleted=item.get('deleted'),
            )
            for item in data
        ]


# =============================================================================
# Factory Function
# =============================================================================


def create_x_ads_client(
    consumer_key: str | None = None,
    consumer_secret: str | None = None,
    access_token: str | None = None,
    access_token_secret: str | None = None,
) -> XAdsClient:
    """
    Create an XAdsClient instance.

    If credentials not provided, reads from environment:
    - X_ADS_CONSUMER_KEY
    - X_ADS_CONSUMER_SECRET
    - X_ADS_ACCESS_TOKEN
    - X_ADS_ACCESS_TOKEN_SECRET
    """
    import os

    return XAdsClient(
        consumer_key=consumer_key or os.environ['X_ADS_CONSUMER_KEY'],
        consumer_secret=consumer_secret or os.environ['X_ADS_CONSUMER_SECRET'],
        access_token=access_token or os.environ['X_ADS_ACCESS_TOKEN'],
        access_token_secret=access_token_secret
        or os.environ['X_ADS_ACCESS_TOKEN_SECRET'],
    )
