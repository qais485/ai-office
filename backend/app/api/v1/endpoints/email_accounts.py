"""Email account API endpoints with ownership checks and input validation."""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.email_account import EmailAccountCreate, EmailAccountUpdate, EmailAccountResponse
from app.services.email_account_service import EmailAccountService
from app.api.deps import get_current_active_user
from app.models.user import User

import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class SendEmailRequest(BaseModel):
    to_address: EmailStr
    subject: str
    body: str


class TestImapRequest(BaseModel):
    host: str
    port: int = 993
    username: str
    password: str
    use_ssl: bool = True


class TestSmtpRequest(BaseModel):
    host: str
    port: int = 465
    username: str
    password: str
    use_ssl: bool = True


@router.get("/", response_model=list[EmailAccountResponse])
def list_accounts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = EmailAccountService(db)
    accounts = service.get_accounts(user_id=current_user.id)
    logger.debug("Listed %d email accounts", len(accounts))
    return accounts


@router.get("/{account_id}", response_model=EmailAccountResponse)
def get_account(
    account_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = EmailAccountService(db)
    account = service.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if account.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    logger.debug("Retrieved email account %s", account_id)
    return account


@router.post("/", response_model=EmailAccountResponse)
def create_account(
    data: EmailAccountCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = EmailAccountService(db)
    created = service.create_account(user_id=current_user.id, data=data)
    logger.info("Created email account %s", created.id)
    return created


@router.put("/{account_id}", response_model=EmailAccountResponse)
def update_account(
    account_id: UUID,
    data: EmailAccountUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = EmailAccountService(db)
    account = service.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if account.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    updated = service.update_account(account_id, data)
    logger.info("Updated email account %s", account_id)
    return updated


@router.delete("/{account_id}")
def delete_account(
    account_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = EmailAccountService(db)
    account = service.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if account.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    service.delete_account(account_id)
    logger.info("Deleted email account %s", account_id)
    return {"message": "Account deleted"}


@router.post("/{account_id}/sync")
def sync_account(
    account_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = EmailAccountService(db)
    account = service.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if account.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    result = service.sync_account(account_id)
    logger.info("Synced email account %s", account_id)
    return result


@router.post("/{account_id}/send")
def send_email(
    account_id: UUID,
    data: SendEmailRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    service = EmailAccountService(db)
    account = service.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if account.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    result = service.send_reply(
        account_id=account_id,
        to_address=data.to_address,
        subject=data.subject,
        body=data.body,
    )
    if not result["success"]:
        logger.error("Failed to send email from account %s: %s", account_id, result["error"])
        raise HTTPException(status_code=500, detail=result["error"])
    logger.info("Sent email from account %s to %s", account_id, data.to_address)
    return {"message": "Email sent"}


@router.post("/test-imap")
def test_imap(
    data: TestImapRequest,
    current_user: User = Depends(get_current_active_user),
):
    service = EmailAccountService(None)
    success, message = service.test_imap(
        data.host, data.port, data.username, data.password, data.use_ssl
    )
    logger.info("Tested IMAP connection: %s", success)
    return {"success": success, "message": message}


@router.post("/test-smtp")
def test_smtp(
    data: TestSmtpRequest,
    current_user: User = Depends(get_current_active_user),
):
    service = EmailAccountService(None)
    success, message = service.test_smtp(
        data.host, data.port, data.username, data.password, data.use_ssl
    )
    logger.info("Tested SMTP connection: %s", success)
    return {"success": success, "message": message}
