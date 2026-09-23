"""Meta WhatsApp Cloud API webhook and interactive booking messages."""

from __future__ import annotations

import hashlib
import hmac
import os
import threading
import asyncio
from typing import Any, Optional

import httpx
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse


router = APIRouter(prefix="/api/webhook/meta", tags=["Meta WhatsApp"])
_seen_message_ids: set[str] = set()
_seen_lock = threading.Lock()
_MAX_SEEN_MESSAGE_IDS = 10_000


def _is_duplicate(message_id: str) -> bool:
    with _seen_lock:
        if message_id in _seen_message_ids:
            return True
        if len(_seen_message_ids) >= _MAX_SEEN_MESSAGE_IDS:
            _seen_message_ids.clear()
        _seen_message_ids.add(message_id)
        return False


def _valid_signature(raw_body: bytes, signature: Optional[str]) -> bool:
    app_secret = os.getenv("META_APP_SECRET")
    if not app_secret or not signature or not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        app_secret.encode("utf-8"), raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _messages(payload: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            result.extend(change.get("value", {}).get("messages", []))
    return result


def _incoming_text(message: dict[str, Any]) -> Optional[str]:
    message_type = message.get("type")
    if message_type == "text":
        return message.get("text", {}).get("body", "").strip()
    if message_type == "interactive":
        interactive = message.get("interactive", {})
        if interactive.get("type") == "button_reply":
            return {
                "booking_confirm": "YES",
                "booking_cancel": "NO",
            }.get(interactive.get("button_reply", {}).get("id"), "")
        if interactive.get("type") == "list_reply":
            reply_id = interactive.get("list_reply", {}).get("id", "")
            if reply_id.startswith("date:"):
                return reply_id.removeprefix("date:")
            if reply_id.startswith("slot:"):
                parts = reply_id.split(":", 2)
                return parts[-1] if len(parts) == 3 else ""
    return None


def _graph_config() -> tuple[str, str, str]:
    access_token = os.getenv("WA_ACCESS_TOKEN") or os.getenv("META_WA_ACCESS_TOKEN")
    phone_number_id = os.getenv("WA_PHONE_NUMBER_ID") or os.getenv("META_PHONE_NUMBER_ID")
    version = os.getenv("META_GRAPH_API_VERSION", "v21.0")
    if not access_token or not phone_number_id:
        raise RuntimeError("WA_ACCESS_TOKEN and WA_PHONE_NUMBER_ID must be configured")
    return access_token, phone_number_id, version


async def _send_interactive(to: str, interactive: dict[str, Any]) -> None:
    access_token, phone_number_id, version = _graph_config()
    url = f"https://graph.facebook.com/{version}/{phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {access_token}"}
    payload = {"messaging_product": "whatsapp", "to": to, "type": "interactive", "interactive": interactive}
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()


async def _send_text(to: str, body: str) -> None:
    access_token, phone_number_id, version = _graph_config()
    url = f"https://graph.facebook.com/{version}/{phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {access_token}"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"preview_url": False, "body": body},
    }
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()


async def _send_booking_confirmation_buttons(to: str, body: str) -> None:
    await _send_interactive(
        to,
        {
            "type": "button",
            "body": {"text": body[:1024]},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": "booking_confirm", "title": "Confirm"}},
                    {"type": "reply", "reply": {"id": "booking_cancel", "title": "Cancel"}},
                ]
            },
        },
    )


async def _send_date_list(to: str, dates: list[str], body: str) -> None:
    rows = [
        {"id": f"date:{date}", "title": date, "description": "Available collection date"}
        for date in dates[:10]
    ]
    await _send_interactive(
        to,
        {
            "type": "list",
            "body": {"text": body[:1024]},
            "action": {"button": "Choose date", "sections": [{"title": "Available dates", "rows": rows}]},
        },
    )


async def _send_slot_list(to: str, slots: list[dict[str, Any]], body: str) -> None:
    rows = [
        {
            "id": f"slot:{slot['appointment_date']}:{slot['start_time']}",
            "title": f"{slot['start_time']}–{slot['end_time']}",
            "description": f"{slot['available_capacity']} spot(s) available",
        }
        for slot in slots[:10]
    ]
    await _send_interactive(
        to,
        {
            "type": "list",
            "body": {"text": body[:1024]},
            "action": {"button": "Choose time", "sections": [{"title": "Available slots", "rows": rows}]},
        },
    )


async def process_message(message: dict[str, Any]) -> None:
    from backend.booking_service import get_or_create_booking_session
    from backend.main import ChatRequest, handle_chat
    from backend.store import get_store

    sender = message.get("from")
    text = _incoming_text(message)
    if not sender or not text:
        return

    response = await asyncio.to_thread(
        handle_chat,
        ChatRequest(session_id=f"meta:{sender}", message=text, source="whatsapp_meta"),
    )
    state = get_or_create_booking_session(f"meta:{sender}")
    missing = state.get_missing_field()

    if state.status == "awaiting_confirmation":
        await _send_booking_confirmation_buttons(sender, response.reply)
    elif missing == "preferred_date":
        dates = get_store().list_available_dates()
        if dates:
            await _send_date_list(sender, dates, response.reply)
        else:
            await _send_text(sender, response.reply)
    elif missing == "preferred_time" and response.available_slots:
        await _send_slot_list(sender, response.available_slots, response.reply)
    else:
        await _send_text(sender, response.reply)


async def process_payload(payload: dict[str, Any]) -> None:
    for message in _messages(payload):
        try:
            await process_message(message)
        except Exception:
            # Webhook acknowledgement has already been sent; failures are
            # intentionally isolated so one message cannot stop the batch.
            continue


@router.get("")
async def verify_meta_webhook(request: Request):
    params = request.query_params
    verify_token = os.getenv("WA_VERIFY_TOKEN")
    if (
        params.get("hub.mode") != "subscribe"
        or not verify_token
        or params.get("hub.verify_token") != verify_token
    ):
        raise HTTPException(status_code=403, detail="Webhook verification failed")
    return PlainTextResponse(params["hub.challenge"])


@router.post("")
async def receive_meta_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: Optional[str] = Header(default=None),
):
    raw_body = await request.body()
    if not _valid_signature(raw_body, x_hub_signature_256):
        raise HTTPException(status_code=403, detail="Invalid webhook signature")
    payload = await request.json()
    new_messages = [message for message in _messages(payload) if message.get("id") and not _is_duplicate(message["id"])]
    if new_messages:
        background_tasks.add_task(process_payload, {"entry": [{"changes": [{"value": {"messages": new_messages}}]}]})
    return JSONResponse({"status": "accepted"}, status_code=200)
