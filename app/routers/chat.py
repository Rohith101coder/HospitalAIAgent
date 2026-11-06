from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import limiter
from app.schemas.chat import ChatRequest, ChatResponse
from app.agent.agent import HospitalAgent

router = APIRouter(prefix="/api/chat", tags=["Chat"])


@router.post("", response_model=ChatResponse)
@limiter.limit("30/minute")
def chat_endpoint(
    request: Request,
    payload: ChatRequest,
    db: Session = Depends(get_db)
):
    """
    Main conversational endpoint for patient interaction with the hospital AI front-desk agent.
    Stateless: accepts patient message and optional recent React state conversation history.
    Does not require or create login accounts, passwords, or backend chat sessions.
    Supports English, Telugu, Hindi, and transliterations.
    """
    agent = HospitalAgent(db=db)
    result = agent.process_message(message=payload.message, history=payload.history)

    return ChatResponse(
        reply=result["reply"],
        language=result.get("language", "en"),
        is_emergency=result.get("is_emergency", False)
    )
