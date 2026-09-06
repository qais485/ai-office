from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from uuid import UUID


class EmailBase(BaseModel):
    from_address: str
    to_address: str
    subject: str
    body: str


class EmailCreate(EmailBase):
    agent_id: Optional[UUID] = None
    conversation_id: Optional[str] = None
    category: Optional[str] = None
    account_id: Optional[UUID] = None


class EmailUpdate(BaseModel):
    status: Optional[str] = None
    draft_response: Optional[str] = None
    agent_id: Optional[UUID] = None
    category: Optional[str] = None


class EmailResponse(EmailBase):
    id: UUID
    status: str
    agent_id: Optional[UUID] = None
    conversation_id: Optional[str] = None
    draft_response: Optional[str] = None
    category: Optional[str] = None
    account_id: Optional[UUID] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
