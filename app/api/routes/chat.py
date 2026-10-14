from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from app.models.schemas import ChatRequest, ChatResponse
from app.services.chat_service import ChatService

from app.core.auth import get_current_user, AuthenticatedUser

router = APIRouter(prefix="/chat", tags=["Chat"])

@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest, user: AuthenticatedUser = Depends(get_current_user)):
    service = ChatService()
    return service.chat(request)

@router.post("/stream")
async def chat_stream(request: ChatRequest, user: AuthenticatedUser = Depends(get_current_user)):
    service = ChatService()
    return StreamingResponse(
        service.chat_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
