from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response

from app.dependencies import get_current_user_id, get_grant_service
from app.schemas.grant import (
    GrantActiveCheck,
    GrantCreate,
    GrantRead,
    GrantsListResponse,
)
from app.services.grants import GrantService

router = APIRouter(tags=["grants"])


@router.post("/grants", response_model=GrantRead, status_code=201)
async def create_grant(
    payload: GrantCreate,
    service: GrantService = Depends(get_grant_service),
    current_user_id: UUID = Depends(get_current_user_id),
):
    return await service.create_grant(data=payload, current_user_id=current_user_id)


@router.get("/grants", response_model=GrantsListResponse)
async def list_grants(
    document_id: UUID | None = Query(default=None),
    granted_to_user_id: UUID | None = Query(default=None),
    active_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: GrantService = Depends(get_grant_service),
):
    items, total = await service.list_grants(
        document_id=document_id,
        granted_to_user_id=granted_to_user_id,
        active_only=active_only,
        limit=limit,
        offset=offset,
    )
    return GrantsListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/grants/{grant_id}", response_model=GrantRead)
async def get_grant(
    grant_id: UUID,
    service: GrantService = Depends(get_grant_service),
):
    return await service.get_grant(grant_id=grant_id)


@router.delete("/grants/{grant_id}", status_code=204)
async def revoke_grant(
    grant_id: UUID,
    service: GrantService = Depends(get_grant_service),
    current_user_id: UUID = Depends(get_current_user_id),
):
    await service.revoke_grant(grant_id=grant_id, current_user_id=current_user_id)
    return Response(status_code=204)


@router.get("/grants/{grant_id}/check", response_model=GrantActiveCheck)
async def check_grant_active(
    grant_id: UUID,
    service: GrantService = Depends(get_grant_service),
):
    return GrantActiveCheck(active=await service.check_active(grant_id=grant_id))
