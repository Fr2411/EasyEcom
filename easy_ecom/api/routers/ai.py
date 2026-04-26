from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Request, Response

from easy_ecom.api.dependencies import ServiceContainer, get_authenticated_user, get_container
from easy_ecom.api.schemas.ai import (
    AIAgentSettingsResponse,
    AIAgentSettingsUpdateRequest,
    AICatalogSearchRequest,
    AICatalogSearchResponse,
    AIConfirmOrderRequest,
    AIConfirmOrderResponse,
    AIConversationStateRequest,
    AIConversationStateResponse,
    AIHandoffRequest,
    AIHandoffResponse,
    AIToolContextResponse,
    AIVariantAvailabilityRequest,
    AIVariantAvailabilityResponse,
    PublicChatMessageRequest,
    PublicChatMessageResponse,
)
from easy_ecom.core.config import settings
from easy_ecom.core.errors import ApiException
from easy_ecom.domain.models.auth import AuthenticatedUser

router = APIRouter(prefix="/ai", tags=["ai"])


def _api_base_url(request: Request) -> str:
    return str(request.base_url).rstrip("/")


def require_ai_tool_auth(
    token: str | None = Header(default=None, alias="X-EasyEcom-AI-Tool-Token"),
) -> None:
    if not settings.ai_tool_api_secret:
        raise ApiException(
            status_code=503,
            code="AI_TOOL_AUTH_NOT_CONFIGURED",
            message="AI tool API secret is not configured",
        )
    if token != settings.ai_tool_api_secret:
        raise ApiException(status_code=401, code="AI_TOOL_UNAUTHORIZED", message="Unauthorized AI tool request")


@router.get("/settings", response_model=AIAgentSettingsResponse)
def get_ai_agent_settings(
    request: Request,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> AIAgentSettingsResponse:
    return AIAgentSettingsResponse.model_validate(
        container.ai_chat.get_settings(user, api_base_url=_api_base_url(request))
    )


@router.put("/settings", response_model=AIAgentSettingsResponse)
def update_ai_agent_settings(
    payload: AIAgentSettingsUpdateRequest,
    request: Request,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> AIAgentSettingsResponse:
    return AIAgentSettingsResponse.model_validate(
        container.ai_chat.update_settings(
            user,
            api_base_url=_api_base_url(request),
            request_id=getattr(request.state, "request_id", None),
            payload=payload.model_dump(),
        )
    )


@router.get("/chat/widget.js", include_in_schema=False)
def website_chat_widget() -> Response:
    return Response(content=WIDGET_JS, media_type="application/javascript")


@router.post("/chat/public/{widget_key}/messages", response_model=PublicChatMessageResponse)
def public_chat_message(
    widget_key: str,
    payload: PublicChatMessageRequest,
    request: Request,
    container: ServiceContainer = Depends(get_container),
) -> PublicChatMessageResponse:
    client_ip = request.client.host if request.client else ""
    result = container.ai_chat.handle_public_message(
        widget_key=widget_key,
        browser_session_id=payload.browser_session_id,
        message=payload.message,
        customer=payload.customer.model_dump() if payload.customer else None,
        metadata=payload.metadata,
        origin=request.headers.get("origin", ""),
        client_ip=client_ip,
        tool_base_url=f"{_api_base_url(request)}/ai/tools",
    )
    return PublicChatMessageResponse.model_validate(result)


@router.get("/tools/context", response_model=AIToolContextResponse, dependencies=[Depends(require_ai_tool_auth)])
def ai_tool_context(
    client_id: str,
    conversation_id: str,
    container: ServiceContainer = Depends(get_container),
) -> AIToolContextResponse:
    return AIToolContextResponse.model_validate(
        container.ai_chat.tool_context(client_id=client_id, conversation_id=conversation_id)
    )


@router.post("/tools/catalog/search", response_model=AICatalogSearchResponse, dependencies=[Depends(require_ai_tool_auth)])
def ai_tool_catalog_search(
    payload: AICatalogSearchRequest,
    container: ServiceContainer = Depends(get_container),
) -> AICatalogSearchResponse:
    return AICatalogSearchResponse.model_validate(
        container.ai_chat.tool_catalog_search(
            client_id=payload.client_id,
            conversation_id=payload.conversation_id,
            query=payload.query,
            location_id=payload.location_id,
            include_out_of_stock=payload.include_out_of_stock,
            limit=payload.limit,
        )
    )


@router.post(
    "/tools/variant/availability",
    response_model=AIVariantAvailabilityResponse,
    dependencies=[Depends(require_ai_tool_auth)],
)
def ai_tool_variant_availability(
    payload: AIVariantAvailabilityRequest,
    container: ServiceContainer = Depends(get_container),
) -> AIVariantAvailabilityResponse:
    return AIVariantAvailabilityResponse.model_validate(
        container.ai_chat.tool_variant_availability(
            client_id=payload.client_id,
            conversation_id=payload.conversation_id,
            variant_id=payload.variant_id,
            quantity=payload.quantity,
            location_id=payload.location_id,
        )
    )


@router.post(
    "/tools/conversation/state",
    response_model=AIConversationStateResponse,
    dependencies=[Depends(require_ai_tool_auth)],
)
def ai_tool_conversation_state(
    payload: AIConversationStateRequest,
    container: ServiceContainer = Depends(get_container),
) -> AIConversationStateResponse:
    return AIConversationStateResponse.model_validate(
        container.ai_chat.tool_conversation_state(
            client_id=payload.client_id,
            conversation_id=payload.conversation_id,
            status=payload.status,
            latest_intent=payload.latest_intent,
            latest_summary=payload.latest_summary,
            customer=payload.customer.model_dump() if payload.customer else None,
            metadata=payload.metadata,
        )
    )


@router.post(
    "/tools/orders/confirm-from-chat",
    response_model=AIConfirmOrderResponse,
    dependencies=[Depends(require_ai_tool_auth)],
)
def ai_tool_confirm_order_from_chat(
    payload: AIConfirmOrderRequest,
    container: ServiceContainer = Depends(get_container),
) -> AIConfirmOrderResponse:
    return AIConfirmOrderResponse.model_validate(
        container.ai_chat.tool_confirm_order_from_chat(
            client_id=payload.client_id,
            conversation_id=payload.conversation_id,
            customer=payload.customer.model_dump(),
            lines=[item.model_dump() for item in payload.lines],
            customer_confirmed=payload.customer_confirmed,
            confirmation_text=payload.confirmation_text,
            location_id=payload.location_id,
            notes=payload.notes,
        )
    )


@router.post("/tools/handoff", response_model=AIHandoffResponse, dependencies=[Depends(require_ai_tool_auth)])
def ai_tool_handoff(
    payload: AIHandoffRequest,
    container: ServiceContainer = Depends(get_container),
) -> AIHandoffResponse:
    return AIHandoffResponse.model_validate(
        container.ai_chat.tool_handoff(
            client_id=payload.client_id,
            conversation_id=payload.conversation_id,
            reason=payload.reason,
            summary=payload.summary,
        )
    )


WIDGET_JS = r"""
(function () {
  var script = document.currentScript;
  if (!script) return;
  var widgetKey = script.getAttribute('data-easy-ecom-widget-key');
  if (!widgetKey) return;
  var apiBase = new URL(script.src).origin;
  var storageKey = 'easy_ecom_chat_session_' + widgetKey;
  var sessionId = localStorage.getItem(storageKey);
  if (!sessionId) {
    sessionId = 'web_' + Math.random().toString(36).slice(2) + Date.now().toString(36);
    localStorage.setItem(storageKey, sessionId);
  }

  var root = document.createElement('div');
  root.style.position = 'fixed';
  root.style.right = '18px';
  root.style.bottom = '18px';
  root.style.zIndex = '2147483647';
  root.style.fontFamily = 'Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';

  var button = document.createElement('button');
  button.type = 'button';
  button.textContent = 'Chat';
  button.style.border = '0';
  button.style.borderRadius = '999px';
  button.style.padding = '12px 18px';
  button.style.background = '#111827';
  button.style.color = '#fff';
  button.style.boxShadow = '0 14px 40px rgba(15, 23, 42, .24)';
  button.style.cursor = 'pointer';

  var panel = document.createElement('section');
  panel.style.display = 'none';
  panel.style.width = 'min(360px, calc(100vw - 36px))';
  panel.style.height = '440px';
  panel.style.background = '#fff';
  panel.style.border = '1px solid #d8dee8';
  panel.style.borderRadius = '10px';
  panel.style.boxShadow = '0 22px 70px rgba(15, 23, 42, .24)';
  panel.style.overflow = 'hidden';

  var header = document.createElement('div');
  header.textContent = 'EasyEcom assistant';
  header.style.padding = '12px 14px';
  header.style.fontWeight = '700';
  header.style.background = '#111827';
  header.style.color = '#fff';

  var messages = document.createElement('div');
  messages.style.height = '328px';
  messages.style.overflow = 'auto';
  messages.style.padding = '12px';
  messages.style.background = '#f8fafc';

  var form = document.createElement('form');
  form.style.display = 'flex';
  form.style.gap = '8px';
  form.style.padding = '10px';
  form.style.borderTop = '1px solid #e5e7eb';

  var input = document.createElement('input');
  input.type = 'text';
  input.placeholder = 'Type your message';
  input.style.flex = '1';
  input.style.border = '1px solid #d1d5db';
  input.style.borderRadius = '8px';
  input.style.padding = '10px';

  var send = document.createElement('button');
  send.type = 'submit';
  send.textContent = 'Send';
  send.style.border = '0';
  send.style.borderRadius = '8px';
  send.style.padding = '10px 12px';
  send.style.background = '#111827';
  send.style.color = '#fff';
  send.style.cursor = 'pointer';

  function addMessage(text, direction) {
    var bubble = document.createElement('div');
    bubble.textContent = text;
    bubble.style.maxWidth = '82%';
    bubble.style.margin = direction === 'outbound' ? '8px 0 8px auto' : '8px auto 8px 0';
    bubble.style.padding = '9px 10px';
    bubble.style.borderRadius = '8px';
    bubble.style.background = direction === 'outbound' ? '#111827' : '#fff';
    bubble.style.color = direction === 'outbound' ? '#fff' : '#111827';
    bubble.style.border = direction === 'outbound' ? '0' : '1px solid #e5e7eb';
    messages.appendChild(bubble);
    messages.scrollTop = messages.scrollHeight;
  }

  button.addEventListener('click', function () {
    var open = panel.style.display !== 'none';
    panel.style.display = open ? 'none' : 'block';
    button.style.display = open ? 'block' : 'none';
    if (!open) input.focus();
  });

  header.addEventListener('click', function () {
    panel.style.display = 'none';
    button.style.display = 'block';
  });

  form.addEventListener('submit', function (event) {
    event.preventDefault();
    var text = input.value.trim();
    if (!text) return;
    input.value = '';
    addMessage(text, 'outbound');
    fetch(apiBase + '/ai/chat/public/' + encodeURIComponent(widgetKey) + '/messages', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ browser_session_id: sessionId, message: text })
    })
      .then(function (response) { return response.json(); })
      .then(function (payload) {
        var reply = payload.reply_text || 'Our team will follow up shortly.';
        addMessage(reply, 'inbound');
      })
      .catch(function () {
        addMessage('Our team will follow up shortly.', 'inbound');
      });
  });

  form.appendChild(input);
  form.appendChild(send);
  panel.appendChild(header);
  panel.appendChild(messages);
  panel.appendChild(form);
  root.appendChild(panel);
  root.appendChild(button);
  document.body.appendChild(root);
})();
"""
