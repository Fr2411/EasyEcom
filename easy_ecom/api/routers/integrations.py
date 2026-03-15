from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from easy_ecom.api.dependencies import ServiceContainer, get_authenticated_user, get_container
from easy_ecom.api.schemas.sales_agent import (
    ChannelIntegrationsResponse,
    ChannelLocationsResponse,
    WhatsAppMetaIntegrationRequest,
    WhatsAppMetaIntegrationResponse,
)
from easy_ecom.domain.models.auth import AuthenticatedUser


router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/channels", response_model=ChannelIntegrationsResponse)
def list_channels(
    client_id: str | None = Query(default=None),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> ChannelIntegrationsResponse:
    return ChannelIntegrationsResponse(items=container.sales_agent.list_integrations(user, target_client_id=client_id))


@router.get("/channels/locations", response_model=ChannelLocationsResponse)
def list_channel_locations(
    client_id: str | None = Query(default=None),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> ChannelLocationsResponse:
    return ChannelLocationsResponse(items=container.sales_agent.list_available_locations(user, target_client_id=client_id))


@router.put("/channels/whatsapp/meta", response_model=WhatsAppMetaIntegrationResponse)
def upsert_whatsapp_meta(
    payload: WhatsAppMetaIntegrationRequest,
    client_id: str | None = Query(default=None),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> WhatsAppMetaIntegrationResponse:
    return WhatsAppMetaIntegrationResponse.model_validate(
        container.sales_agent.upsert_whatsapp_integration(user, payload.model_dump(), target_client_id=client_id)
    )
