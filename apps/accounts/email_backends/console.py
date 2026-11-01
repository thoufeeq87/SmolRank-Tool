import sys

from django.core.mail.backends.base import BaseEmailBackend


class ConsoleEmailBackend(BaseEmailBackend):
    """Dev backend: print the plain-text body as-is.

    Django's stock console backend prints raw MIME, which wraps long lines with a
    trailing "=" (quoted-printable) and breaks magic links when copied.
    """

    def __init__(self, *args, stream=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.stream = stream or sys.stdout

    def send_messages(self, email_messages):
        for message in email_messages:
            self.stream.write(
                f"\n{'-' * 60}\nTo: {', '.join(message.to)}\nSubject: {message.subject}\n\n"
                f"{message.body}\n{'-' * 60}\n"
            )
        self.stream.flush()
        return len(email_messages)
