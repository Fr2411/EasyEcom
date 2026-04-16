from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from easy_ecom.api.dependencies import ServiceContainer, get_authenticated_user, get_container, require_module_access
from easy_ecom.api.schemas.sales_agent import (
    ChannelDiagnosticsEnvelopeResponse,
    ChannelIntegrationsResponse,
    ChannelLocationsResponse,
    ChannelRunDiagnosticsResponse,
    ChannelSmokeRequest,
    ChannelSmokeResponse,
    WhatsAppMetaIntegrationRequest,
    WhatsAppMetaIntegrationResponse,
)
from easy_ecom.domain.models.auth import AuthenticatedUser


router = APIRouter(
    prefix="/integrations",
    tags=["integrations"],
    dependencies=[Depends(require_module_access("Sales Agent"))],
)


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


@router.post("/channels/whatsapp/meta/validate", response_model=ChannelDiagnosticsEnvelopeResponse)
def validate_whatsapp_meta(
    payload: WhatsAppMetaIntegrationRequest,
    client_id: str | None = Query(default=None),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> ChannelDiagnosticsEnvelopeResponse:
    return ChannelDiagnosticsEnvelopeResponse.model_validate(
        container.sales_agent.validate_whatsapp_integration(user, payload.model_dump(), target_client_id=client_id)
    )


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


@router.post("/channels/{channel_id}/run-diagnostics", response_model=ChannelRunDiagnosticsResponse)
def run_channel_diagnostics(
    channel_id: str,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> ChannelRunDiagnosticsResponse:
    return ChannelRunDiagnosticsResponse.model_validate(
        container.sales_agent.run_channel_diagnostics(user, channel_id)
    )


@router.post("/channels/{channel_id}/send-smoke", response_model=ChannelSmokeResponse)
def send_channel_smoke(
    channel_id: str,
    payload: ChannelSmokeRequest,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> ChannelSmokeResponse:
    return ChannelSmokeResponse.model_validate(
        container.sales_agent.send_channel_smoke(user, channel_id, payload.model_dump())
    )
