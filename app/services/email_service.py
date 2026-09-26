from email.message import EmailMessage

import aiosmtplib

from app.core.config import settings


class EmailService:
    """Service responsible for sending transactional emails."""

    async def send_email(
        self,
        *,
        to_email: str,
        subject: str,
        body: str,
    ) -> None:
        if not settings.smtp_username:
            raise RuntimeError("SMTP username is not configured")

        if not settings.smtp_password:
            raise RuntimeError("SMTP password is not configured")

        from_email = settings.smtp_from_email or settings.smtp_username

        message = EmailMessage()
        message["From"] = (
            f"{settings.smtp_from_name} <{from_email}>"
            if settings.smtp_from_name
            else from_email
        )
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(body)

        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            start_tls=settings.smtp_use_tls,
        )

    async def send_otp_email(
        self,
        *,
        to_email: str,
        otp: str,
    ) -> None:
        subject = "Your AImNest verification code"

        body = f"""Hello,

Your AImNest verification code is:

{otp}

This code will expire in {settings.otp_expires_seconds // 60} minutes.

If you did not request this code, you can safely ignore this email.

Regards,
AImNest Team
"""

        await self.send_email(
            to_email=to_email,
            subject=subject,
            body=body,
        )