from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, Response

from easy_ecom.api.dependencies import ServiceContainer, get_container


router = APIRouter(prefix="/public/webhooks", tags=["public-webhooks"])


@router.get("/whatsapp/{webhook_key}")
async def verify_whatsapp_webhook(
    webhook_key: str,
    mode: str = Query(alias="hub.mode"),
    verify_token: str = Query(alias="hub.verify_token"),
    challenge: str = Query(alias="hub.challenge"),
    container: ServiceContainer = Depends(get_container),
) -> Response:
    result = container.sales_agent.verify_whatsapp_webhook(
        webhook_key,
        mode=mode,
        verify_token=verify_token,
        challenge=challenge,
    )
    return Response(content=result, media_type="text/plain")


@router.post("/whatsapp/{webhook_key}")
async def receive_whatsapp_webhook(
    webhook_key: str,
    request: Request,
    container: ServiceContainer = Depends(get_container),
) -> dict[str, object]:
    raw_body = await request.body()
    payload = await request.json()
    signature = request.headers.get("X-Hub-Signature-256")
    return container.sales_agent.handle_whatsapp_webhook(
        webhook_key,
        raw_body=raw_body,
        signature=signature,
        payload=payload,
    )
