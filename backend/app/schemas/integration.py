from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
from uuid import UUID


class IntegrationBase(BaseModel):
    name: str
    display_name: str
    description: Optional[str] = None
    icon_url: Optional[str] = None
    auth_type: str
    config_schema: Optional[dict] = None
    capabilities: Optional[dict] = None
    is_active: bool = True
    oauth2_authorize_url: Optional[str] = None
    oauth2_token_url: Optional[str] = None
    oauth2_client_id_key: Optional[str] = None
    oauth2_client_secret_key: Optional[str] = None
    oauth2_scopes: Optional[str] = None
    oauth2_redirect_path: Optional[str] = None


class IntegrationCreate(IntegrationBase):
    pass


class IntegrationResponse(IntegrationBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class IntegrationAccountBase(BaseModel):
    integration_id: UUID
    display_name: Optional[str] = None
    credentials: Optional[dict] = None
    config: Optional[dict] = None
    status: str = "connected"


class IntegrationAccountCreate(IntegrationAccountBase):
    pass


class IntegrationAccountUpdate(BaseModel):
    display_name: Optional[str] = None
    credentials: Optional[dict] = None
    config: Optional[dict] = None
    status: Optional[str] = None


class ConnectRequest(BaseModel):
    credentials: dict
    display_name: Optional[str] = None
    config: Optional[dict] = None


class OAuth2AuthorizeResponse(BaseModel):
    authorization_url: str
    state: str


class IntegrationAccountResponse(IntegrationAccountBase):
    id: UUID
    user_id: UUID
    last_sync_at: Optional[str] = None
    oauth2_token_expiry: Optional[str] = None
    oauth2_scope: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
