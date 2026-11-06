from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ChatMessageHistoryItem(BaseModel):
    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., min_length=1)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="Patient message text")
    history: Optional[List[ChatMessageHistoryItem]] = Field(default_factory=list, description="Recent conversation history maintained in frontend React state")


class ChatResponse(BaseModel):
    reply: str
    language: Optional[str] = "en"
    is_emergency: bool = False
