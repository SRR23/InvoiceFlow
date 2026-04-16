"""
Send outbound email via Resend HTTP API (no SMTP).

Requires ``RESEND_API_KEY`` and a verified ``from`` address per Resend rules
"""
from __future__ import annotations

import base64
import logging
from typing import Any

import resend
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.message import EmailMessage

logger = logging.getLogger(__name__)


class ResendEmailBackend(BaseEmailBackend):
    """
    Django email backend that delivers messages through Resend's API.

    Maps :class:`~django.core.mail.EmailMessage` to Resend's ``Emails.send`` payload.
    """

    def __init__(self, fail_silently: bool = False, **kwargs: Any) -> None:
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.api_key = getattr(settings, 'RESEND_API_KEY', '') or ''

    def send_messages(self, email_messages: list[EmailMessage]) -> int:
        if not email_messages:
            return 0
        if not self.api_key.strip():
            logger.error(
                'RESEND_API_KEY is not set; cannot send email via Resend. '
                'Set it in the environment (and DEFAULT_FROM_EMAIL to an allowed sender).'
            )
            if not self.fail_silently:
                raise ValueError('RESEND_API_KEY is required for ResendEmailBackend')
            return 0

        resend.api_key = self.api_key.strip()
        num_sent = 0
        for message in email_messages:
            if self._send(message):
                num_sent += 1
        return num_sent

    def _send(self, message: EmailMessage) -> bool:
        try:
            payload = self._build_payload(message)
        except ValueError as exc:
            logger.exception('Invalid email message for Resend: %s', exc)
            if not self.fail_silently:
                raise
            return False

        try:
            resend.Emails.send(payload)
        except Exception:
            logger.exception('Resend API error while sending email')
            if not self.fail_silently:
                raise
            return False
        return True

    def _build_payload(self, message: EmailMessage) -> dict[str, Any]:
        recipients = [addr for addr in (message.to or []) if addr]
        if not recipients:
            raise ValueError('Email message has no recipients in "to"')

        from_email = message.from_email or getattr(
            settings, 'DEFAULT_FROM_EMAIL', 'noreply@localhost'
        )
        if not from_email:
            raise ValueError('No from_email and DEFAULT_FROM_EMAIL is empty')

        subject = message.subject or ''

        html_body: str | None = None
        plain_body = message.body or ''
        if message.alternatives:
            for content, mimetype in message.alternatives:
                if mimetype == 'text/html':
                    html_body = content
                    break

        payload: dict[str, Any] = {
            'from': from_email,
            'to': recipients,
            'subject': subject,
        }

        if html_body is not None:
            payload['html'] = html_body
            if plain_body.strip():
                payload['text'] = plain_body
        else:
            payload['text'] = plain_body if plain_body else '(no body)'

        if message.cc:
            payload['cc'] = [a for a in message.cc if a]
        if message.bcc:
            payload['bcc'] = [a for a in message.bcc if a]
        reply_to = getattr(message, 'reply_to', None) or []
        if reply_to:
            payload['reply_to'] = reply_to[0]

        attachments = self._attachments_for_resend(message)
        if attachments:
            payload['attachments'] = attachments

        return payload

    def _attachments_for_resend(self, message: EmailMessage) -> list[dict[str, Any]]:
        """Convert Django attachments to Resend's attachment format."""
        out: list[dict[str, Any]] = []
        for attachment in message.attachments:
            if not isinstance(attachment, tuple):
                logger.warning('Skipping non-tuple attachment for Resend backend')
                continue
            if len(attachment) == 3:
                filename, content, mimetype = attachment
            elif len(attachment) == 2:
                filename, content = attachment
                mimetype = None
            else:
                continue

            if isinstance(content, str):
                content = content.encode('utf-8')

            item: dict[str, Any] = {
                'filename': filename or 'attachment',
                'content': base64.b64encode(content).decode('ascii'),
            }
            if mimetype:
                item['content_type'] = mimetype
            out.append(item)
        return out
