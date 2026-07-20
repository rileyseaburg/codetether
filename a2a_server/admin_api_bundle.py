"""Cohesive bundle of legacy and focused administrative routers."""

from fastapi import APIRouter

from a2a_server.admin_api import router as legacy_router
from a2a_server.agent_identity_api import router as identity_router


router = APIRouter()
router.include_router(legacy_router)
router.include_router(identity_router)
