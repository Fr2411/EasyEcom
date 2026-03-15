from __future__ import annotations

from fastapi import APIRouter, Depends

from easy_ecom.api.dependencies import ServiceContainer, get_authenticated_user, get_container
from easy_ecom.api.schemas.sales_agent import (
    ChannelIntegrationsResponse,
    WhatsAppMetaIntegrationRequest,
    WhatsAppMetaIntegrationResponse,
)
from easy_ecom.domain.models.auth import AuthenticatedUser


router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/channels", response_model=ChannelIntegrationsResponse)
def list_channels(
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> ChannelIntegrationsResponse:
    return ChannelIntegrationsResponse(items=container.sales_agent.list_integrations(user))


@router.put("/channels/whatsapp/meta", response_model=WhatsAppMetaIntegrationResponse)
def upsert_whatsapp_meta(
    payload: WhatsAppMetaIntegrationRequest,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> WhatsAppMetaIntegrationResponse:
    return WhatsAppMetaIntegrationResponse.model_validate(
        container.sales_agent.upsert_whatsapp_integration(user, payload.model_dump())
    )
