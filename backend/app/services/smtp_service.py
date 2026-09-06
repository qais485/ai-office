"""Hardened SMTP service with try/finally, timeouts, logging, SSRF protection, and header injection prevention."""
import smtplib
import logging
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

SMTP_TIMEOUT = 30

BLOCKED_HOSTS = {
    "localhost", "127.0.0.1", "0.0.0.0", "::1",
    "169.254.169.254",  # AWS metadata
    "metadata.google.internal",  # GCP metadata
}


def _is_safe_host(host: str) -> bool:
    """Validate that the host is not an internal/metadata service (SSRF protection)."""
    host_lower = host.lower().strip()
    if host_lower in BLOCKED_HOSTS:
        return False
    if host_lower.startswith("10.") or host_lower.startswith("172.") or host_lower.startswith("192.168."):
        return False
    if host_lower.startswith("169.254."):
        return False
    for blocked in BLOCKED_HOSTS:
        if blocked in host_lower:
            return False
    return True


def _sanitize_header(value: str) -> str:
    """Remove CRLF characters from header values to prevent header injection."""
    if not value:
        return value
    return re.sub(r'[\r\n]+', '', value).strip()


class SmtpService:
    def __init__(self, host: str, port: int, username: str, password: str, use_ssl: bool = True):
        if not _is_safe_host(host):
            raise ValueError(f"Connection to host '{host}' is not allowed (SSRF protection)")
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_ssl = use_ssl

    def send_email(
        self,
        to_address: str,
        subject: str,
        body: str,
        from_address: Optional[str] = None,
        is_html: bool = False,
    ) -> Tuple[bool, str]:
        to_address = _sanitize_header(to_address)
        subject = _sanitize_header(subject)
        from_address = _sanitize_header(from_address) if from_address else None

        if not to_address or "@" not in to_address:
            return False, "Invalid recipient address"

        msg = MIMEMultipart()
        msg["From"] = from_address or self.username
        msg["To"] = to_address
        msg["Subject"] = subject

        content_type = "html" if is_html else "plain"
        msg.attach(MIMEText(body, content_type, "utf-8"))

        server = None
        try:
            if self.use_ssl:
                server = smtplib.SMTP_SSL(self.host, self.port, timeout=SMTP_TIMEOUT)
            else:
                server = smtplib.SMTP(self.host, self.port, timeout=SMTP_TIMEOUT)
                server.starttls()

            server.login(self.username, self.password)
            server.sendmail(msg["From"], [to_address], msg.as_string())
            logger.info(f"SMTP email sent to {to_address} via {self.host}")
            return True, "Email sent successfully"
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP auth failed for {self.host}: {e}")
            return False, "Authentication failed"
        except smtplib.SMTPRecipientsRefused as e:
            logger.error(f"SMTP recipient refused: {e}")
            return False, "Recipient refused"
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error sending to {to_address}: {e}")
            return False, "SMTP error occurred"
        except (OSError, TimeoutError) as e:
            logger.error(f"SMTP connection timeout/error to {self.host}: {e}")
            return False, "Connection error"
        except Exception as e:
            logger.error(f"SMTP unexpected error: {e}")
            return False, "Unexpected error"
        finally:
            if server:
                try:
                    server.quit()
                except Exception:
                    pass

    def test_connection(self) -> Tuple[bool, str]:
        server = None
        try:
            if self.use_ssl:
                server = smtplib.SMTP_SSL(self.host, self.port, timeout=SMTP_TIMEOUT)
            else:
                server = smtplib.SMTP(self.host, self.port, timeout=SMTP_TIMEOUT)
                server.starttls()

            server.login(self.username, self.password)
            return True, "SMTP connection successful"
        except smtplib.SMTPAuthenticationError as e:
            return False, "Authentication failed"
        except (OSError, TimeoutError) as e:
            return False, "Connection error"
        except Exception as e:
            return False, "Connection failed"
        finally:
            if server:
                try:
                    server.quit()
                except Exception:
                    pass
