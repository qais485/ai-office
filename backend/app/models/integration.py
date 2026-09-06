from sqlalchemy import Column, String, Boolean, Text, JSON

from app.models.base import BaseModel


class Integration(BaseModel):
    __tablename__ = "integrations"

    name = Column(String(100), nullable=False, unique=True)
    display_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    icon_url = Column(String(500), nullable=True)
    auth_type = Column(String(50), nullable=False)
    config_schema = Column(JSON, nullable=True)
    capabilities = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # OAuth2 configuration (generic — not provider-specific)
    oauth2_authorize_url = Column(String(500), nullable=True)
    oauth2_token_url = Column(String(500), nullable=True)
    oauth2_client_id_key = Column(String(100), nullable=True)
    oauth2_client_secret_key = Column(String(100), nullable=True)
    oauth2_scopes = Column(Text, nullable=True)
    oauth2_redirect_path = Column(String(200), nullable=True)
