"""Hardened IMAP service with timeouts, logging, connection recovery, and SSRF protection."""
import imaplib
import email
import logging
import socket
from email.header import decode_header
from datetime import datetime
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

IMAP_TIMEOUT = 30
IMAP_FETCH_TIMEOUT = 60
IMAP_MAX_MESSAGE_SIZE = 10 * 1024 * 1024  # 10MB

BLOCKED_HOSTS = {
    "localhost", "127.0.0.1", "0.0.0.0", "::1",
    "169.254.169.254",  # AWS metadata
    "metadata.google.internal",  # GCP metadata
    "169.254.169.254.nip.io",
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
    # Block metadata endpoints
    for blocked in BLOCKED_HOSTS:
        if blocked in host_lower:
            return False
    return True


class ImapService:
    def __init__(self, host: str, port: int, username: str, password: str, use_ssl: bool = True):
        if not _is_safe_host(host):
            raise ValueError(f"Connection to host '{host}' is not allowed (SSRF protection)")
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_ssl = use_ssl
        self._connection: Optional[imaplib.IMAP4_SSL | imaplib.IMAP4] = None

    def connect(self) -> bool:
        try:
            if self.use_ssl:
                self._connection = imaplib.IMAP4_SSL(self.host, self.port, timeout=IMAP_TIMEOUT)
            else:
                self._connection = imaplib.IMAP4(self.host, self.port, timeout=IMAP_TIMEOUT)
            self._connection.login(self.username, self.password)
            logger.info(f"IMAP connected to {self.host}:{self.port}")
            return True
        except imaplib.IMAP4.error as e:
            logger.error(f"IMAP auth failed for {self.host}: {e}")
            self._connection = None
            return False
        except (OSError, TimeoutError) as e:
            logger.error(f"IMAP connection failed to {self.host}:{self.port}: {e}")
            self._connection = None
            return False
        except Exception as e:
            logger.error(f"IMAP unexpected error: {e}")
            self._connection = None
            return False

    def disconnect(self):
        if self._connection:
            try:
                self._connection.logout()
            except Exception:
                pass
            self._connection = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
        return False

    def fetch_unseen(self, folder: str = "INBOX", limit: int = 50) -> List[Dict]:
        if not self._connection:
            logger.warning("IMAP fetch_unseen called without connection")
            return []

        results = []
        try:
            status, _ = self._connection.select(folder, readonly=True)
            if status != "OK":
                logger.error(f"IMAP failed to select folder '{folder}'")
                return []

            status, data = self._connection.search(None, "UNSEEN")
            if status != "OK":
                logger.error("IMAP search failed")
                return []

            msg_ids = data[0].split()
            if not msg_ids:
                return []

            msg_ids = msg_ids[-limit:]
            logger.info(f"IMAP fetching {len(msg_ids)} unseen messages from {folder}")

            for msg_id in msg_ids:
                try:
                    status, msg_data = self._connection.fetch(msg_id, "(RFC822)")
                    if status != "OK" or not msg_data or not msg_data[0]:
                        continue

                    raw_email = msg_data[0][1]
                    if len(raw_email) > IMAP_MAX_MESSAGE_SIZE:
                        logger.warning(f"IMAP message {msg_id} too large, skipping")
                        continue

                    msg = email.message_from_bytes(raw_email)
                    parsed = self._parse_message(msg, msg_id.decode())
                    if parsed:
                        results.append(parsed)
                except (TimeoutError, OSError) as e:
                    logger.warning(f"IMAP failed to fetch message {msg_id}: {e}")
                    continue
                except Exception as e:
                    logger.warning(f"IMAP unexpected error fetching message {msg_id}: {e}")
                    continue

            logger.info(f"IMAP fetched {len(results)} messages from {folder}")
            return results

        except (TimeoutError, OSError) as e:
            logger.error(f"IMAP fetch timeout/error: {e}")
            self.disconnect()
            return []
        except Exception as e:
            logger.error(f"IMAP fetch error: {e}")
            self.disconnect()
            return []

    def mark_as_seen(self, msg_id: str, folder: str = "INBOX"):
        if not self._connection:
            return
        try:
            self._connection.select(folder)
            self._connection.store(msg_id.encode(), "+FLAGS", "\\Seen")
        except Exception as e:
            logger.warning(f"IMAP failed to mark message {msg_id} as seen: {e}")

    def _parse_message(self, msg: email.message.Message, msg_id: str) -> Optional[Dict]:
        try:
            subject = self._decode_header(msg["Subject"] or "")
            from_addr = self._decode_header(msg["From"] or "")
            to_addr = self._decode_header(msg["To"] or "")
            date_str = msg["Date"] or ""

            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    if content_type == "text/plain":
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or "utf-8"
                            body = payload.decode(charset, errors="replace")
                            break
                    elif content_type == "text/html" and not body:
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or "utf-8"
                            body = payload.decode(charset, errors="replace")
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    charset = msg.get_content_charset() or "utf-8"
                    body = payload.decode(charset, errors="replace")

            return {
                "imap_id": msg_id,
                "from_address": from_addr,
                "to_address": to_addr,
                "subject": subject,
                "body": body,
                "date": date_str,
            }
        except Exception as e:
            logger.warning(f"IMAP failed to parse message {msg_id}: {e}")
            return None

    def _decode_header(self, header: str) -> str:
        decoded_parts = decode_header(header)
        result = []
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                result.append(part.decode(encoding or "utf-8", errors="replace"))
            else:
                result.append(part)
        return " ".join(result)

    def test_connection(self) -> Tuple[bool, str]:
        if self.connect():
            self.disconnect()
            return True, "IMAP connection successful"
        return False, "Failed to connect to IMAP server"
