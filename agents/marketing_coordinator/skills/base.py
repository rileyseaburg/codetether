"""
Base Skill class for Marketing Coordinator skills.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import aiohttp

logger = logging.getLogger(__name__)


class BaseSkill(ABC):
    """Base class for all Marketing Coordinator skills."""

    def __init__(self, config: Any):
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self.session is None or self.session.closed:
            connector = aiohttp.TCPConnector(
                limit=20,
                limit_per_host=10,
            )
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=60),
                headers={'Content-Type': 'application/json'},
            )
        return self.session

    async def _call_spotlessbinco_api(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        use_rust: bool = False,
    ) -> Dict[str, Any]:
        """Call the spotlessbinco API."""
        session = await self._get_session()

        base_url = (
            self.config.spotlessbinco_rust_url
            if use_rust
            else self.config.spotlessbinco_api_url
        )
        url = f'{base_url}{endpoint}'

        try:
            async with session.request(method, url, json=data) as resp:
                if resp.status in (200, 201):
                    return await resp.json()
                else:
                    error = await resp.text()
                    logger.error(f'API error {resp.status}: {error}')
                    return {'error': error, 'status': resp.status}
        except Exception as e:
            logger.error(f'API call failed: {e}')
            return {'error': str(e)}

    async def _call_orpc(self, procedure: str, data: Dict) -> Dict[str, Any]:
        """Call an oRPC procedure on the spotlessbinco API."""
        return await self._call_spotlessbinco_api(
            method='POST',
            endpoint=f'/orpc/{procedure}',
            data=data,
        )

    @abstractmethod
    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the skill with the given task."""
        pass
