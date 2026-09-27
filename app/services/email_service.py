from email.message import EmailMessage

import aiosmtplib

from app.core.config import settings


class EmailService:
    """
    Email service for AImNest.

    Handles:
    - OTP emails
    - Welcome emails
    - Generic emails
    """

    async def send_email(
        self,
        *,
        to_email: str,
        subject: str,
        body: str,
        html_body: str | None = None,
    ) -> None:
        """
        Send an email using the configured SMTP server.
        """

        if not settings.smtp_host:
            raise RuntimeError("SMTP host is not configured")

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

        # Plain-text fallback
        message.set_content(body)

        # HTML version
        if html_body:
            message.add_alternative(
                html_body,
                subtype="html",
            )

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
        otp_code: str,
        expires_minutes: int = 3,
    ) -> None:
        """
        Send OTP verification email.
        """

        subject = "Your AImNest Verification Code"

        body = f"""
Hello,

Your AImNest verification code is:

{otp_code}

This code will expire in {expires_minutes} minutes.

If you did not request this code, you can safely ignore this email.

Regards,
AImNest Team
""".strip()

        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>AImNest Verification Code</title>
</head>

<body
    style="
        margin:0;
        padding:0;
        background-color:#f4f6f8;
        font-family:'Courier New', Courier, monospace;
    "
>

    <div
        style="
            max-width:600px;
            margin:40px auto;
            background:#ffffff;
            border-radius:12px;
            padding:40px;
            box-sizing:border-box;
        "
    >

        <!-- AImNest Header -->
        <div
            style="
                text-align:center;
                margin-bottom:30px;
                font-family:'Courier New', Courier, monospace;
            "
        >
            <div
                style="
                    font-size:30px;
                    font-weight:bold;
                    letter-spacing:1px;
                "
            >
                AImNest
            </div>

            <div
                style="
                    margin-top:8px;
                    font-size:14px;
                    color:#666666;
                "
            >
                Learn. Build. Grow.
            </div>
        </div>


        <!-- Main Heading -->
        <h2
            style="
                font-family:'Courier New', Courier, monospace;
                color:#222222;
                margin-bottom:20px;
            "
        >
            Verify your email
        </h2>


        <p
            style="
                font-family:'Courier New', Courier, monospace;
                color:#444444;
                line-height:1.7;
            "
        >
            Hello,
        </p>


        <p
            style="
                font-family:'Courier New', Courier, monospace;
                color:#444444;
                line-height:1.7;
            "
        >
            Use the verification code below to continue with your
            AImNest account.
        </p>


        <!-- OTP -->
        <div
            style="
                margin:30px 0;
                text-align:center;
            "
        >

            <div
                style="
                    display:inline-block;
                    padding:18px 30px;
                    border-radius:10px;
                    background:#f0f2f5;
                    font-family:'Courier New', Courier, monospace;
                    font-size:32px;
                    font-weight:bold;
                    letter-spacing:8px;
                    color:#111111;
                "
            >
                {otp_code}
            </div>

        </div>


        <p
            style="
                font-family:'Courier New', Courier, monospace;
                color:#555555;
                line-height:1.7;
            "
        >
            This code will expire in
            <strong>{expires_minutes} minutes</strong>.
        </p>


        <p
            style="
                font-family:'Courier New', Courier, monospace;
                color:#777777;
                font-size:13px;
                line-height:1.7;
            "
        >
            If you did not request this verification code,
            you can safely ignore this email.
        </p>


        <!-- Footer -->
        <div
            style="
                margin-top:35px;
                padding-top:20px;
                border-top:1px solid #eeeeee;
                text-align:center;
                font-family:'Courier New', Courier, monospace;
                color:#777777;
                font-size:13px;
            "
        >
            AImNest Team
        </div>

    </div>

</body>
</html>
""".strip()

        await self.send_email(
            to_email=to_email,
            subject=subject,
            body=body,
            html_body=html_body,
        )

    async def send_welcome_email(
        self,
        *,
        to_email: str,
        user_name: str | None = None,
    ) -> None:
        """
        Send welcome email after successful OTP verification.
        """

        display_name = user_name.strip() if user_name else "there"

        subject = "Welcome to AImNest 🚀"

        body = f"""
Hello {display_name},

Welcome to AImNest! 🚀

Your journey starts here.

Learn by doing, solve real-world challenges,
build your skills, and turn every problem into progress.

Start small. Stay curious. Keep building.

Welcome aboard,

AImNest Team
""".strip()

        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Welcome to AImNest</title>
</head>

<body
    style="
        margin:0;
        padding:0;
        background-color:#f4f6f8;
        font-family:'Courier New', Courier, monospace;
    "
>

    <div
        style="
            max-width:600px;
            margin:40px auto;
            background:#ffffff;
            border-radius:12px;
            padding:40px;
            box-sizing:border-box;
        "
    >

        <!-- AImNest Header -->
        <div
            style="
                text-align:center;
                margin-bottom:35px;
                font-family:'Courier New', Courier, monospace;
            "
        >

            <div
                style="
                    font-size:32px;
                    font-weight:bold;
                    letter-spacing:1px;
                    color:#111111;
                "
            >
                AImNest
            </div>

            <div
                style="
                    margin-top:8px;
                    font-size:14px;
                    color:#666666;
                "
            >
                Learn. Build. Grow.
            </div>

        </div>


        <!-- Welcome -->
        <h1
            style="
                font-family:'Courier New', Courier, monospace;
                color:#222222;
                font-size:26px;
                margin-bottom:20px;
            "
        >
            Welcome to AImNest 🚀
        </h1>


        <p
            style="
                font-family:'Courier New', Courier, monospace;
                color:#444444;
                line-height:1.8;
                font-size:15px;
            "
        >
            Hello {display_name},
        </p>


        <p
            style="
                font-family:'Courier New', Courier, monospace;
                color:#444444;
                line-height:1.8;
                font-size:15px;
            "
        >
            Your journey starts here.
        </p>


        <p
            style="
                font-family:'Courier New', Courier, monospace;
                color:#444444;
                line-height:1.8;
                font-size:15px;
            "
        >
            Learn by doing, solve real-world challenges,
            build your skills, and turn every problem into progress.
        </p>


        <!-- Motivation Box -->
        <div
            style="
                margin:30px 0;
                padding:22px;
                border-radius:10px;
                background:#f0f2f5;
                font-family:'Courier New', Courier, monospace;
                text-align:center;
            "
        >

            <div
                style="
                    font-size:17px;
                    font-weight:bold;
                    color:#222222;
                    line-height:1.7;
                "
            >
                Start small.<br>
                Stay curious.<br>
                Keep building.
            </div>

        </div>


        <p
            style="
                font-family:'Courier New', Courier, monospace;
                color:#444444;
                line-height:1.8;
                font-size:15px;
            "
        >
            We're excited to have you with us.
        </p>


        <p
            style="
                font-family:'Courier New', Courier, monospace;
                color:#444444;
                line-height:1.8;
                font-size:15px;
                margin-top:30px;
            "
        >
            Welcome aboard,
        </p>


        <p
            style="
                font-family:'Courier New', Courier, monospace;
                font-weight:bold;
                color:#222222;
                font-size:15px;
            "
        >
            AImNest Team
        </p>


        <!-- Footer -->
        <div
            style="
                margin-top:40px;
                padding-top:20px;
                border-top:1px solid #eeeeee;
                text-align:center;
                font-family:'Courier New', Courier, monospace;
                color:#777777;
                font-size:12px;
            "
        >
            Learn. Build. Grow. 🚀
        </div>

    </div>

</body>
</html>
""".strip()

        await self.send_email(
            to_email=to_email,
            subject=subject,
            body=body,
            html_body=html_body,
        )


email_service = EmailService()