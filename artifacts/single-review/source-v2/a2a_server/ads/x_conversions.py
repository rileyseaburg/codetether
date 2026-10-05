"""
X (Twitter) Ads Conversion API Client.

Server-side conversion tracking for X advertising platform.
Implements the X Conversion API (CAPI) for sending events
directly from CodeTether's first-party analytics.

References:
- https://developer.x.com/en/docs/x-ads-api/conversion-api
- https://developer.x.com/en/docs/x-ads-api/conversion-api/guides/conversions-api-with-click-id
"""

import asyncio
import hashlib
import hmac
import time
from datetime import datetime
from typing import Any, Literal
from urllib.parse import quote

import httpx
from pydantic import BaseModel, Field


class XConversionEvent(BaseModel):
    """X Conversion API event payload."""
    
    event_type: Literal[
        "PAGE_VIEW", "PURCHASE", "SIGNUP", "LEAD", 
        "DOWNLOAD", "CUSTOM", "ADD_TO_CART", "CHECKOUT_INITIATED",
        "CONTENT_VIEW", "SEARCH"
    ] = Field(description="Type of conversion event")
    
    event_time: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the event occurred (UTC)"
    )
    
    # User identifiers (at least one required)
    twclid: str | None = Field(None, description="X Click ID from URL parameter")
    email: str | None = Field(None, description="Email (will be hashed)")
    phone: str | None = Field(None, description="Phone (will be hashed)")
    
    # Event details
    event_id: str | None = Field(None, description="Unique event ID for deduplication")
    value: float | None = Field(None, description="Monetary value (e.g., purchase amount)")
    currency: str = Field("USD", description="Currency code")
    
    # Additional context
    contents: list[dict] | None = Field(None, description="Product/content details")
    conversion_id: str | None = Field(None, description="Your internal conversion ID")


class XConversionClient:
    """
    Client for X Ads Conversion API.
    
    Example usage:
        client = XConversionClient(
            pixel_id="abc123",
            consumer_key="...",
            consumer_secret="...",
            access_token="...",
            access_token_secret="..."
        )
        
        await client.send_conversion(XConversionEvent(
            event_type="SIGNUP",
            twclid="xyz123",
            email="user@example.com"
        ))
    """
    
    BASE_URL = "https://ads-api.twitter.com/12"
    
    def __init__(
        self,
        pixel_id: str,
        consumer_key: str,
        consumer_secret: str,
        access_token: str,
        access_token_secret: str,
        test_mode: bool = False
    ):
        self.pixel_id = pixel_id
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.access_token = access_token
        self.access_token_secret = access_token_secret
        self.test_mode = test_mode
    
    def _hash_identifier(self, value: str) -> str:
        """SHA256 hash for PII fields."""
        normalized = value.lower().strip()
        return hashlib.sha256(normalized.encode()).hexdigest()
    
    def _generate_oauth_signature(
        self, 
        method: str, 
        url: str, 
        params: dict[str, str]
    ) -> str:
        """Generate OAuth 1.0a signature for X API."""
        # Sort and encode parameters
        sorted_params = sorted(params.items())
        param_string = "&".join(
            f"{quote(k, safe='')}={quote(v, safe='')}" 
            for k, v in sorted_params
        )
        
        # Create signature base string
        base_string = "&".join([
            method.upper(),
            quote(url, safe=''),
            quote(param_string, safe='')
        ])
        
        # Create signing key
        signing_key = f"{quote(self.consumer_secret, safe='')}&{quote(self.access_token_secret, safe='')}"
        
        # Generate HMAC-SHA1 signature
        signature = hmac.new(
            signing_key.encode(),
            base_string.encode(),
            hashlib.sha1
        ).digest()
        
        import base64
        return base64.b64encode(signature).decode()
    
    def _build_auth_header(self, method: str, url: str) -> str:
        """Build OAuth 1.0a Authorization header."""
        import secrets
        
        oauth_params = {
            "oauth_consumer_key": self.consumer_key,
            "oauth_nonce": secrets.token_hex(16),
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_timestamp": str(int(time.time())),
            "oauth_token": self.access_token,
            "oauth_version": "1.0"
        }
        
        # Generate signature
        signature = self._generate_oauth_signature(method, url, oauth_params)
        oauth_params["oauth_signature"] = signature
        
        # Build header
        header_parts = [
            f'{k}="{quote(v, safe="")}"' 
            for k, v in sorted(oauth_params.items())
        ]
        return "OAuth " + ", ".join(header_parts)
    
    def _build_payload(self, event: XConversionEvent) -> dict[str, Any]:
        """Build the API payload from an event."""
        payload: dict[str, Any] = {
            "conversions": [{
                "conversion_time": event.event_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "event_id": event.event_id or f"ct_{int(time.time() * 1000)}",
                "identifiers": []
            }]
        }
        
        conversion = payload["conversions"][0]
        
        # Add identifiers
        if event.twclid:
            conversion["identifiers"].append({
                "twclid": event.twclid
            })
        
        if event.email:
            conversion["identifiers"].append({
                "hashed_email": self._hash_identifier(event.email)
            })
        
        if event.phone:
            conversion["identifiers"].append({
                "hashed_phone_number": self._hash_identifier(event.phone)
            })
        
        # Add optional fields
        if event.value is not None:
            conversion["value"] = str(event.value)
            conversion["currency"] = event.currency
        
        if event.contents:
            conversion["contents"] = event.contents
        
        if event.conversion_id:
            conversion["conversion_id"] = event.conversion_id
        
        return payload
    
    async def send_conversion(
        self, 
        event: XConversionEvent
    ) -> dict[str, Any]:
        """
        Send a conversion event to X Ads API.
        
        Returns the API response or raises on error.
        """
        url = f"{self.BASE_URL}/measurement/conversions/{self.pixel_id}"
        
        # Add event type to URL
        url = f"{url}?conversion_type={event.event_type}"
        
        if self.test_mode:
            url += "&test_mode=true"
        
        payload = self._build_payload(event)
        auth_header = self._build_auth_header("POST", url.split("?")[0])
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=payload,
                headers={
                    "Authorization": auth_header,
                    "Content-Type": "application/json"
                },
                timeout=30.0
            )
            
            response.raise_for_status()
            return response.json()
    
    async def send_batch(
        self, 
        events: list[XConversionEvent]
    ) -> list[dict[str, Any]]:
        """Send multiple conversions (batched by event_type)."""
        # Group by event type (X API requires same type per call)
        by_type: dict[str, list[XConversionEvent]] = {}
        for event in events:
            by_type.setdefault(event.event_type, []).append(event)
        
        results = []
        for event_type, typed_events in by_type.items():
            # X API supports up to 1000 per batch
            for chunk in self._chunk(typed_events, 1000):
                # Combine into single payload
                combined_payload = {"conversions": []}
                for event in chunk:
                    single = self._build_payload(event)
                    combined_payload["conversions"].extend(single["conversions"])
                
                url = f"{self.BASE_URL}/measurement/conversions/{self.pixel_id}?conversion_type={event_type}"
                if self.test_mode:
                    url += "&test_mode=true"
                
                auth_header = self._build_auth_header("POST", url.split("?")[0])
                
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        url,
                        json=combined_payload,
                        headers={
                            "Authorization": auth_header,
                            "Content-Type": "application/json"
                        },
                        timeout=60.0
                    )
                    response.raise_for_status()
                    results.append(response.json())
        
        return results
    
    @staticmethod
    def _chunk(lst: list, size: int):
        """Yield successive chunks from list."""
        for i in range(0, len(lst), size):
            yield lst[i:i + size]


# Convenience function for direct use
async def forward_conversion_to_x(
    event_type: str,
    twclid: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    value: float | None = None,
    currency: str = "USD",
    event_id: str | None = None,
    pixel_id: str | None = None,
    consumer_key: str | None = None,
    consumer_secret: str | None = None,
    access_token: str | None = None,
    access_token_secret: str | None = None,
    test_mode: bool = False
) -> dict[str, Any]:
    """
    Send a single conversion event to X Ads.
    
    If credentials not provided, reads from environment:
    - X_ADS_PIXEL_ID
    - X_ADS_CONSUMER_KEY
    - X_ADS_CONSUMER_SECRET
    - X_ADS_ACCESS_TOKEN
    - X_ADS_ACCESS_TOKEN_SECRET
    """
    import os
    
    client = XConversionClient(
        pixel_id=pixel_id or os.environ["X_ADS_PIXEL_ID"],
        consumer_key=consumer_key or os.environ["X_ADS_CONSUMER_KEY"],
        consumer_secret=consumer_secret or os.environ["X_ADS_CONSUMER_SECRET"],
        access_token=access_token or os.environ["X_ADS_ACCESS_TOKEN"],
        access_token_secret=access_token_secret or os.environ["X_ADS_ACCESS_TOKEN_SECRET"],
        test_mode=test_mode
    )
    
    event = XConversionEvent(
        event_type=event_type,
        twclid=twclid,
        email=email,
        phone=phone,
        value=value,
        currency=currency,
        event_id=event_id
    )
    
    return await client.send_conversion(event)
