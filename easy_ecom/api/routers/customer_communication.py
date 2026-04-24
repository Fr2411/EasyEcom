from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from easy_ecom.api.dependencies import ServiceContainer, get_authenticated_user, get_container, require_module_access
from easy_ecom.api.schemas.common import ModuleOverviewResponse
from easy_ecom.api.schemas.customer_communication import (
    AssistantPlaybookResponse,
    AssistantPlaybookUpdateRequest,
    CustomerChannelResponse,
    CustomerChannelUpsertRequest,
    CustomerCommunicationWorkspaceResponse,
    CustomerConversationDetailResponse,
    ProviderWebhookMessage,
    PublicCustomerChatRequest,
    PublicCustomerChatResponse,
)
from easy_ecom.domain.models.auth import AuthenticatedUser


router = APIRouter(
    prefix="/customer-communication",
    tags=["customer-communication"],
    dependencies=[Depends(require_module_access("Customer Communication"))],
)

public_router = APIRouter(prefix="/public/customer-communication", tags=["public-customer-communication"])


@router.get("/overview", response_model=ModuleOverviewResponse)
def customer_communication_overview(
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> ModuleOverviewResponse:
    return container.customer_communication.overview(user)


@router.get("/workspace", response_model=CustomerCommunicationWorkspaceResponse)
def customer_communication_workspace(
    conversation_id: str | None = Query(default=None),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> CustomerCommunicationWorkspaceResponse:
    return CustomerCommunicationWorkspaceResponse.model_validate(
        container.customer_communication.workspace(user, conversation_id=conversation_id)
    )


@router.put("/playbook", response_model=AssistantPlaybookResponse)
def update_assistant_playbook(
    payload: AssistantPlaybookUpdateRequest,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> AssistantPlaybookResponse:
    return AssistantPlaybookResponse.model_validate(
        container.customer_communication.update_playbook(user, payload.model_dump())
    )


@router.post("/channels", response_model=CustomerChannelResponse)
def create_customer_channel(
    payload: CustomerChannelUpsertRequest,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> CustomerChannelResponse:
    return CustomerChannelResponse.model_validate(
        container.customer_communication.create_channel(user, payload.model_dump())
    )


@router.put("/channels/{channel_id}", response_model=CustomerChannelResponse)
def update_customer_channel(
    channel_id: str,
    payload: CustomerChannelUpsertRequest,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> CustomerChannelResponse:
    return CustomerChannelResponse.model_validate(
        container.customer_communication.update_channel(user, channel_id, payload.model_dump())
    )


@router.post("/conversations/{conversation_id}/escalate", response_model=CustomerConversationDetailResponse)
def escalate_conversation(
    conversation_id: str,
    reason: str = Query(default="Manual escalation"),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> CustomerConversationDetailResponse:
    return CustomerConversationDetailResponse.model_validate(
        container.customer_communication.mark_escalated(user, conversation_id, reason)
    )


@public_router.post("/chat/{channel_key}", response_model=PublicCustomerChatResponse)
def receive_website_chat(
    channel_key: str,
    payload: PublicCustomerChatRequest,
    container: ServiceContainer = Depends(get_container),
) -> PublicCustomerChatResponse:
    return PublicCustomerChatResponse.model_validate(
        container.customer_communication.receive_public_message(
            channel_key=channel_key,
            external_sender_id=payload.external_sender_id,
            message_text=payload.message_text,
            sender_name=payload.sender_name,
            sender_phone=payload.sender_phone,
            sender_email=payload.sender_email,
            provider_event_id=payload.provider_event_id,
            metadata=payload.metadata,
            raw_payload=payload.model_dump(),
        )
    )


@public_router.post("/webhooks/{channel_key}/{provider}", response_model=PublicCustomerChatResponse)
def receive_provider_webhook(
    channel_key: str,
    provider: str,
    payload: ProviderWebhookMessage,
    container: ServiceContainer = Depends(get_container),
) -> PublicCustomerChatResponse:
    return PublicCustomerChatResponse.model_validate(
        container.customer_communication.receive_public_message(
            channel_key=channel_key,
            external_sender_id=payload.external_sender_id,
            message_text=payload.message_text,
            sender_name=payload.sender_name,
            sender_phone=payload.sender_phone,
            sender_email=payload.sender_email,
            provider_event_id=payload.provider_event_id,
            metadata={**payload.metadata, "provider": provider},
            raw_payload=payload.model_dump(),
        )
    )
