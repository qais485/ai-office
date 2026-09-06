"""Email message API endpoints with ownership checks."""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.email import EmailCreate, EmailUpdate, EmailResponse
from app.services.email_service import EmailService
from app.services.email_account_service import EmailAccountService
from app.api.deps import get_current_active_user
from app.models.user import User

import logging

logger = logging.getLogger(__name__)

router = APIRouter()


def _verify_email_ownership(db: Session, email_id: UUID, user_id: UUID):
    """Verify the email belongs to the user's account. Raises 403 if not."""
    service = EmailService(db)
    email = service.get_email(email_id)
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    if email.account_id:
        account_service = EmailAccountService(db)
        account = account_service.get_account(email.account_id)
        if not account or account.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
    return email


@router.get("/", response_model=list[EmailResponse])
def list_emails(
    agent_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = EmailService(db)
    emails = service.get_emails(agent_id=agent_id, user_id=current_user.id)
    logger.debug("Listed %d emails", len(emails))
    return emails


@router.get("/stats")
def get_email_stats(
    agent_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = EmailService(db)
    return service.get_email_stats(agent_id=agent_id, user_id=current_user.id)


@router.get("/{email_id}", response_model=EmailResponse)
def get_email(
    email_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _verify_email_ownership(db, email_id, current_user.id)
    service = EmailService(db)
    email = service.get_email(email_id)
    logger.debug("Retrieved email %s", email_id)
    return email


@router.post("/", response_model=EmailResponse)
def create_email(
    email_data: EmailCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if email_data.account_id:
        account_service = EmailAccountService(db)
        account = account_service.get_account(email_data.account_id)
        if not account or account.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied to this email account")
    service = EmailService(db)
    created = service.create_email(email_data)
    logger.info("Created email %s", created.id)
    return created


@router.put("/{email_id}", response_model=EmailResponse)
def update_email(
    email_id: UUID,
    email_data: EmailUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _verify_email_ownership(db, email_id, current_user.id)
    service = EmailService(db)
    email = service.update_email(email_id, email_data)
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    logger.info("Updated email %s", email_id)
    return email


@router.delete("/{email_id}")
def delete_email(
    email_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _verify_email_ownership(db, email_id, current_user.id)
    service = EmailService(db)
    if not service.delete_email(email_id):
        raise HTTPException(status_code=404, detail="Email not found")
    logger.info("Deleted email %s", email_id)
    return {"message": "Email deleted"}


@router.post("/{email_id}/process", response_model=EmailResponse)
def process_email(
    email_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _verify_email_ownership(db, email_id, current_user.id)
    service = EmailService(db)
    email = service.process_email(email_id)
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    logger.info("Processed email %s", email_id)
    return email
