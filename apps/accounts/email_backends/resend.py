import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail.backends.base import BaseEmailBackend


class ResendError(Exception):
    pass


class ResendEmailBackend(BaseEmailBackend):
    """Send mail through the Resend HTTP API (https://resend.com/docs/api-reference/emails/send-email)."""

    def send_messages(self, email_messages):
        key = settings.RESEND_API_KEY
        if not key:
            if self.fail_silently:
                return 0
            raise ImproperlyConfigured("RESEND_API_KEY is not set.")
        sent = 0
        for message in email_messages:
            try:
                self._send(message, key)
            except Exception:
                if not self.fail_silently:
                    raise
            else:
                sent += 1
        return sent

    def _send(self, message, key):
        payload = {
            "from": message.from_email or settings.DEFAULT_FROM_EMAIL,
            "to": list(message.to),
            "subject": message.subject,
            "text": message.body,
        }
        if message.cc:
            payload["cc"] = list(message.cc)
        if message.bcc:
            payload["bcc"] = list(message.bcc)
        if message.reply_to:
            payload["reply_to"] = list(message.reply_to)
        for content, mimetype in getattr(message, "alternatives", []):
            if mimetype == "text/html":
                payload["html"] = content

        resp = requests.post(
            settings.RESEND_API_URL,
            json=payload,
            headers={"Authorization": f"Bearer {key}"},
            timeout=settings.RESEND_TIMEOUT,
        )
        if resp.status_code >= 400:
            raise ResendError(f"Resend API error (HTTP {resp.status_code}): {resp.text[:200]}")
