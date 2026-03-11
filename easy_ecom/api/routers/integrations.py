from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from easy_ecom.api.dependencies import RequestUser, ServiceContainer, get_container, get_current_user, require_page_access
from easy_ecom.api.schemas.integrations import (
    ChannelIntegrationCreateRequest,
    ChannelIntegrationListResponse,
    ChannelIntegrationPatchRequest,
    ChannelIntegrationResponse,
    ChannelMessageListResponse,
    ConversationDetailResponse,
    ConversationListResponse,
    InboundIngestResponse,
    OutboundPrepareRequest,
    OutboundPrepareResponse,
)
from easy_ecom.core.rbac import ADMIN_MANAGE_USERS_ROLES, has_any_role
from easy_ecom.domain.services.integrations_service import (
    ChannelIntegrationCreate,
    ChannelIntegrationPatch,
    InboundEventPayload,
    IntegrationsService,
    OutboundPreparePayload,
)

router = APIRouter(prefix="/integrations", tags=["integrations"])


def _require_service(container: ServiceContainer) -> IntegrationsService:
    service = getattr(container, "integrations", None)
    if service is None:
        raise HTTPException(status_code=501, detail="Integrations API requires postgres backend")
    return service


def _require_admin_role(user: RequestUser) -> None:
    if not has_any_role(user.roles, ADMIN_MANAGE_USERS_ROLES):
        raise HTTPException(status_code=403, detail="Admin or manager role required")


@router.get("/channels", response_model=ChannelIntegrationListResponse)
def get_channels(
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> ChannelIntegrationListResponse:
    require_page_access(user, "Integrations")
    _require_admin_role(user)
    service = _require_service(container)
    return ChannelIntegrationListResponse(items=[ChannelIntegrationResponse(**row) for row in service.list_integrations(client_id=user.client_id)])


@router.post("/channels", response_model=ChannelIntegrationResponse)
def create_channel(
    payload: ChannelIntegrationCreateRequest,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> ChannelIntegrationResponse:
    require_page_access(user, "Integrations")
    _require_admin_role(user)
    service = _require_service(container)
    try:
        row = service.create_integration(
            client_id=user.client_id,
            created_by_user_id=user.user_id,
            payload=ChannelIntegrationCreate(**payload.model_dump()),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ChannelIntegrationResponse(**row)


@router.patch("/channels/{channel_id}", response_model=ChannelIntegrationResponse)
def patch_channel(
    channel_id: str,
    payload: ChannelIntegrationPatchRequest,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> ChannelIntegrationResponse:
    require_page_access(user, "Integrations")
    _require_admin_role(user)
    if not payload.model_dump(exclude_none=True):
        raise HTTPException(status_code=400, detail="No fields provided")
    service = _require_service(container)
    try:
        row = service.patch_integration(client_id=user.client_id, channel_id=channel_id, payload=ChannelIntegrationPatch(**payload.model_dump(exclude_none=True)))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if row is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    return ChannelIntegrationResponse(**row)


@router.get("/messages", response_model=ChannelMessageListResponse)
def get_messages(
    limit: int = Query(default=50, ge=1, le=100),
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> ChannelMessageListResponse:
    require_page_access(user, "Integrations")
    _require_admin_role(user)
    service = _require_service(container)
    return ChannelMessageListResponse(items=service.list_messages(client_id=user.client_id, limit=limit))


@router.post("/inbound/{provider}", response_model=InboundIngestResponse)
async def inbound_webhook(
    provider: str,
    request: Request,
    container: ServiceContainer = Depends(get_container),
) -> InboundIngestResponse:
    service = _require_service(container)
    channel_id = request.headers.get("x-channel-id", "").strip()
    timestamp = request.headers.get("x-channel-timestamp", "").strip()
    signature = request.headers.get("x-channel-signature", "").strip()
    if not channel_id or not timestamp or not signature:
        raise HTTPException(status_code=401, detail="Missing verification headers")
    if not service.is_recent_timestamp(timestamp):
        raise HTTPException(status_code=401, detail="Timestamp outside verification window")

    body = await request.body()
    try:
        raw_payload = json.loads(body.decode() or "{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Malformed JSON payload") from exc

    try:
        typed_payload = InboundEventPayload(**raw_payload)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid payload: {exc}") from exc

    integration = service.get_active_channel_for_verification(provider=provider, channel_id=channel_id)
    if integration is None:
        raise HTTPException(status_code=401, detail="Unknown or inactive channel")
    if not service.verify_inbound_signature(request_body=body, signature=signature, timestamp=timestamp, secret=integration.inbound_secret):
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        result = service.ingest_inbound_event(provider=provider, channel_id=channel_id, payload=typed_payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return InboundIngestResponse(**result)


@router.post("/outbound/prepare", response_model=OutboundPrepareResponse)
def prepare_outbound(
    payload: OutboundPrepareRequest,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> OutboundPrepareResponse:
    require_page_access(user, "Integrations")
    _require_admin_role(user)
    service = _require_service(container)
    try:
        result = service.prepare_outbound(
            client_id=user.client_id,
            created_by_user_id=user.user_id,
            payload=OutboundPreparePayload(**payload.model_dump()),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return OutboundPrepareResponse(**result)


@router.get("/conversations", response_model=ConversationListResponse)
def get_conversations(
    limit: int = Query(default=50, ge=1, le=100),
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> ConversationListResponse:
    require_page_access(user, "Integrations")
    _require_admin_role(user)
    service = _require_service(container)
    return ConversationListResponse(items=service.list_conversations(client_id=user.client_id, limit=limit))


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
def get_conversation(
    conversation_id: str,
    user: RequestUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> ConversationDetailResponse:
    require_page_access(user, "Integrations")
    _require_admin_role(user)
    service = _require_service(container)
    row = service.get_conversation(client_id=user.client_id, conversation_id=conversation_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ConversationDetailResponse(**row)
