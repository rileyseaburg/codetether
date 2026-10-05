"""
CodeTether Ads Module.

Provides integrations with advertising platforms for:
- Conversion tracking (server-side events)
- Campaign management (via spotlessbinco bridge)
- Audience management

Phase 2 of vertical integration strategy.
"""

from .x_conversions import XConversionClient, XConversionEvent, forward_conversion_to_x
from .conversion_forwarder import ConversionForwarder, create_forwarder

__all__ = [
    'XConversionClient',
    'XConversionEvent', 
    'forward_conversion_to_x',
    'ConversionForwarder',
    'create_forwarder'
]
