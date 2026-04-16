import uuid

from fastapi import APIRouter, Request

from app.core.orchestrator import handle_message

router = APIRouter()


@router.post("/chat")
async def chat_endpoint(request: Request):
    data = await request.json()
    message = data.get("message", "")
    session_id = data.get("session_id") or str(uuid.uuid4())
    return await handle_message(message, session_id)
