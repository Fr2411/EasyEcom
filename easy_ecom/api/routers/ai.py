from __future__ import annotations

import html
import json

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi.responses import HTMLResponse

from easy_ecom.api.dependencies import ServiceContainer, get_authenticated_user, get_container
from easy_ecom.api.schemas.ai import (
    AIAgentSettingsResponse,
    AIAgentSettingsUpdateRequest,
    AICatalogSearchRequest,
    AICatalogSearchResponse,
    AIConfirmOrderRequest,
    AIConfirmOrderResponse,
    AIConversationDetailResponse,
    AIConversationListResponse,
    AIConversationStateRequest,
    AIConversationStateResponse,
    AIConversationStatusUpdateRequest,
    AIHandoffRequest,
    AIHandoffResponse,
    AIToolContextResponse,
    AIVariantAvailabilityRequest,
    AIVariantAvailabilityResponse,
    PublicChatBootstrapResponse,
    PublicChatMessageRequest,
    PublicChatMessageResponse,
)
from easy_ecom.core.config import settings
from easy_ecom.core.errors import ApiException
from easy_ecom.domain.models.auth import AuthenticatedUser

router = APIRouter(prefix="/ai", tags=["ai"])


def _api_base_url(request: Request) -> str:
    return str(request.base_url).rstrip("/")


def render_public_chat_page_html(*, api_base_url: str, widget_key: str, assistant_name: str, opening_message: str) -> str:
    safe_opening_message_json = json.dumps(opening_message).replace("</", "<\\/")
    return (
        PUBLIC_CHAT_PAGE_HTML
        .replace("__EASY_ECOM_API_BASE_URL__", json.dumps(api_base_url))
        .replace("__EASY_ECOM_WIDGET_KEY__", json.dumps(widget_key))
        .replace("__EASY_ECOM_ASSISTANT_NAME__", html.escape(assistant_name))
        .replace("__EASY_ECOM_OPENING_MESSAGE_JSON__", safe_opening_message_json)
    )


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


@router.get("/conversations", response_model=AIConversationListResponse)
def list_ai_conversations(
    limit: int = Query(default=20, ge=1, le=100),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> AIConversationListResponse:
    return AIConversationListResponse.model_validate(container.ai_chat.list_conversations(user, limit=limit))


@router.get("/conversations/{conversation_id}", response_model=AIConversationDetailResponse)
def get_ai_conversation_detail(
    conversation_id: str,
    message_limit: int = Query(default=50, ge=1, le=100),
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> AIConversationDetailResponse:
    return AIConversationDetailResponse.model_validate(
        container.ai_chat.get_conversation_detail(user, conversation_id=conversation_id, message_limit=message_limit)
    )


@router.patch("/conversations/{conversation_id}", response_model=AIConversationDetailResponse)
def update_ai_conversation_status(
    conversation_id: str,
    payload: AIConversationStatusUpdateRequest,
    user: AuthenticatedUser = Depends(get_authenticated_user),
    container: ServiceContainer = Depends(get_container),
) -> AIConversationDetailResponse:
    return AIConversationDetailResponse.model_validate(
        container.ai_chat.update_conversation_status(
            user,
            conversation_id=conversation_id,
            status=payload.status,
            handoff_reason=payload.handoff_reason,
        )
    )


@router.get("/chat/widget.js", include_in_schema=False)
def website_chat_widget() -> Response:
    return Response(content=WIDGET_JS, media_type="application/javascript")


@router.get("/chat/public/{widget_key}/bootstrap", response_model=PublicChatBootstrapResponse, include_in_schema=False)
def public_chat_bootstrap(
    widget_key: str,
    container: ServiceContainer = Depends(get_container),
) -> PublicChatBootstrapResponse:
    return PublicChatBootstrapResponse.model_validate(container.ai_chat.public_chat_bootstrap(widget_key=widget_key))


@router.get("/chat/public/{widget_key}", include_in_schema=False)
def public_chat_page(
    widget_key: str,
    request: Request,
    container: ServiceContainer = Depends(get_container),
) -> HTMLResponse:
    api_base_url = _api_base_url(request)
    bootstrap = container.ai_chat.public_chat_bootstrap(widget_key=widget_key)
    content = render_public_chat_page_html(
        api_base_url=api_base_url,
        widget_key=widget_key,
        assistant_name=str(bootstrap.get("assistant_name", "Store assistant")),
        opening_message=str(bootstrap.get("opening_message", "Hi, how can I help you today?")),
    )
    return HTMLResponse(content=content)


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
        client_message_id=payload.client_message_id,
        message=payload.message,
        customer=payload.customer.model_dump() if payload.customer else None,
        metadata=payload.metadata,
        origin=request.headers.get("origin", ""),
        client_ip=client_ip,
        trusted_origins={_api_base_url(request)},
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
  header.textContent = 'Store assistant';
  header.style.padding = '12px 14px';
  header.style.fontWeight = '700';
  header.style.background = '#111827';
  header.style.color = '#fff';

  var assistantName = 'Store assistant';
  var openingMessage = 'Hi, how can I help you today?';
  var greetingSeeded = false;

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

  function buildClientMessageId() {
    return 'msg_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 10);
  }

  function seedGreeting() {
    if (greetingSeeded) return;
    greetingSeeded = true;
    addMessage(openingMessage, 'inbound');
  }

  function loadBootstrap() {
    return fetch(apiBase + '/ai/chat/public/' + encodeURIComponent(widgetKey) + '/bootstrap')
      .then(function (response) {
        if (!response.ok) throw new Error('bootstrap failed');
        return response.json();
      })
      .then(function (payload) {
        assistantName = (payload && payload.assistant_name) || assistantName;
        openingMessage = (payload && payload.opening_message) || openingMessage;
        header.textContent = assistantName;
      })
      .catch(function () {
        header.textContent = assistantName;
      });
  }

  var bootstrapPromise = loadBootstrap();

  button.addEventListener('click', function () {
    var open = panel.style.display !== 'none';
    panel.style.display = open ? 'none' : 'block';
    button.style.display = open ? 'block' : 'none';
    if (!open) {
      bootstrapPromise.finally(function () {
        seedGreeting();
        input.focus();
      });
    }
  });

  header.addEventListener('click', function () {
    panel.style.display = 'none';
    button.style.display = 'block';
  });

  form.addEventListener('submit', function (event) {
    event.preventDefault();
    var text = input.value.trim();
    if (!text) return;
    var clientMessageId = buildClientMessageId();
    input.value = '';
    addMessage(text, 'outbound');
    fetch(apiBase + '/ai/chat/public/' + encodeURIComponent(widgetKey) + '/messages', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ browser_session_id: sessionId, client_message_id: clientMessageId, message: text })
    })
      .then(function (response) {
        return response.json().then(function (payload) {
          if (!response.ok) {
            throw new Error(payload && payload.error && payload.error.message ? payload.error.message : 'Chat request failed');
          }
          return payload;
        });
      })
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


PUBLIC_CHAT_PAGE_HTML = r"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Store chat</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f3f7f8;
      --panel: #ffffff;
      --text: #112327;
      --muted: #5d7177;
      --border: #dbe5e7;
      --primary: #0f766e;
      --primary-strong: #0a5d57;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--text);
      font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    main {
      width: min(760px, calc(100vw - 28px));
      min-height: 100vh;
      margin: 0 auto;
      display: grid;
      align-content: center;
      padding: 24px 0;
    }
    .chat-shell {
      border: 1px solid var(--border);
      border-radius: 14px;
      overflow: hidden;
      background: var(--panel);
      box-shadow: 0 20px 60px rgba(15, 35, 42, 0.12);
    }
    header {
      padding: 16px 18px;
      background: #112327;
      color: #ffffff;
    }
    header h1 {
      margin: 0;
      font-size: 1.05rem;
    }
    header p {
      margin: 4px 0 0;
      color: rgba(255, 255, 255, 0.72);
      font-size: 0.88rem;
    }
    .customer-fields {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      padding: 14px;
      border-bottom: 1px solid var(--border);
      background: #f8fbfb;
    }
    label {
      display: flex;
      flex-direction: column;
      gap: 5px;
      color: var(--muted);
      font-size: 0.82rem;
    }
    input {
      width: 100%;
      border: 1px solid var(--border);
      border-radius: 9px;
      padding: 10px 11px;
      color: var(--text);
      font: inherit;
    }
    .messages {
      height: min(54vh, 460px);
      min-height: 320px;
      overflow: auto;
      display: flex;
      flex-direction: column;
      gap: 10px;
      padding: 14px;
      background: #f8fafc;
    }
    .message {
      max-width: 82%;
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 10px 12px;
      background: #ffffff;
      line-height: 1.45;
      white-space: pre-wrap;
    }
    .message.customer {
      align-self: flex-end;
      background: #e8f7f3;
      border-color: #c4e8df;
    }
    .message.system {
      align-self: center;
      max-width: 100%;
      color: var(--muted);
      background: transparent;
      border: 0;
      padding: 4px 0;
      font-size: 0.86rem;
    }
    form {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 10px;
      padding: 14px;
      border-top: 1px solid var(--border);
      background: #ffffff;
    }
    form input {
      min-height: 44px;
    }
    button {
      min-height: 44px;
      border: 0;
      border-radius: 9px;
      padding: 0 18px;
      background: var(--primary);
      color: #ffffff;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
    }
    button:disabled {
      opacity: 0.62;
      cursor: not-allowed;
    }
    button:hover:not(:disabled) {
      background: var(--primary-strong);
    }
    @media (max-width: 640px) {
      main {
        width: 100vw;
        min-height: 100vh;
        padding: 0;
      }
      .chat-shell {
        min-height: 100vh;
        border: 0;
        border-radius: 0;
      }
      .customer-fields,
      form {
        grid-template-columns: 1fr;
      }
      .messages {
        height: 50vh;
      }
    }
  </style>
</head>
<body>
  <main>
    <section class="chat-shell" aria-label="Store chat">
      <header>
        <h1>__EASY_ECOM_ASSISTANT_NAME__</h1>
        <p>Send a message and the store assistant will reply here.</p>
      </header>
      <div class="customer-fields">
        <label>Name <input id="customer-name" autocomplete="name" /></label>
        <label>Phone <input id="customer-phone" autocomplete="tel" inputmode="tel" /></label>
        <label>Email <input id="customer-email" autocomplete="email" inputmode="email" /></label>
        <label>Delivery address <input id="customer-address" autocomplete="street-address" /></label>
      </div>
      <div id="messages" class="messages" aria-live="polite"></div>
      <form id="chat-form">
        <input id="message-input" autocomplete="off" placeholder="Type your message" />
        <button id="send-button" type="submit">Send</button>
      </form>
    </section>
  </main>
  <script>
    const apiBaseUrl = __EASY_ECOM_API_BASE_URL__;
    const widgetKey = __EASY_ECOM_WIDGET_KEY__;
    const storageKey = "easy_ecom_chat_session_" + widgetKey;
    let sessionId = localStorage.getItem(storageKey);
    if (!sessionId) {
      sessionId = "web_" + Math.random().toString(36).slice(2) + Date.now().toString(36);
      localStorage.setItem(storageKey, sessionId);
    }

    const messages = document.getElementById("messages");
    const form = document.getElementById("chat-form");
    const input = document.getElementById("message-input");
    const sendButton = document.getElementById("send-button");
    const customerName = document.getElementById("customer-name");
    const customerPhone = document.getElementById("customer-phone");
    const customerEmail = document.getElementById("customer-email");
    const customerAddress = document.getElementById("customer-address");

    function addMessage(text, kind) {
      const item = document.createElement("div");
      item.className = "message " + kind;
      item.textContent = text;
      messages.appendChild(item);
      messages.scrollTop = messages.scrollHeight;
    }

    function buildClientMessageId() {
      return "msg_" + Date.now().toString(36) + "_" + Math.random().toString(36).slice(2, 10);
    }

    addMessage(__EASY_ECOM_OPENING_MESSAGE_JSON__, "assistant");

    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      const text = input.value.trim();
      if (!text) return;
      const clientMessageId = buildClientMessageId();
      input.value = "";
      addMessage(text, "customer");
      sendButton.disabled = true;
      try {
        const response = await fetch(apiBaseUrl + "/ai/chat/public/" + encodeURIComponent(widgetKey) + "/messages", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            browser_session_id: sessionId,
            client_message_id: clientMessageId,
            message: text,
            customer: {
              name: customerName.value.trim(),
              phone: customerPhone.value.trim(),
              email: customerEmail.value.trim(),
              address: customerAddress.value.trim()
            },
            metadata: { source: "standalone_chat_link" }
          })
        });
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload && payload.error && payload.error.message ? payload.error.message : "Chat request failed");
        }
        addMessage(payload.reply_text || "The store assistant could not reply right now.", "assistant");
      } catch (error) {
        addMessage(error instanceof Error ? error.message : "Unable to send message right now.", "system");
      } finally {
        sendButton.disabled = false;
        input.focus();
      }
    });
  </script>
</body>
</html>
"""
