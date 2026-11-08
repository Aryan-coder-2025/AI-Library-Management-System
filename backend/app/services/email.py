"""
Transactional Email & SMTP Infrastructure for Athenaeum Academic Platform.

Features:
- Configurable SMTP delivery via standard environment variables.
- Authenticated SMTP with STARTTLS and SSL support.
- Connection and operation timeouts to prevent hanging processes.
- Dual-format transactional templates (high-contrast HTML and plain text).
- Sanitized operational error logging: never exposes passwords, tokens, or full reset URLs.
- Graceful degradation when email is disabled or SMTP is unreachable.
"""
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
import logging
import smtplib
from typing import Optional

from app.config import get_settings

logger = logging.getLogger("athenaeum.email")


def obfuscate_email(email: str) -> str:
    """Safely masks an email address for logging (e.g., j***e@university.edu)."""
    if not email or "@" not in email:
        return "invalid-email"
    user_part, domain = email.split("@", 1)
    if len(user_part) <= 2:
        masked_user = user_part[0] + "*"
    else:
        masked_user = user_part[0] + "*" * (len(user_part) - 2) + user_part[-1]
    return f"{masked_user}@{domain}"


def build_password_reset_text(recipient_name: str, reset_url: str, expire_minutes: int) -> str:
    """Builds a plain-text password reset email."""
    name = recipient_name.strip() if recipient_name else "Scholar"
    return (
        f"Hello {name},\n\n"
        f"A password reset was requested for your Athenaeum Academic Library account.\n\n"
        f"To choose a new password, open the following secure link in your web browser:\n"
        f"{reset_url}\n\n"
        f"This link will expire in {expire_minutes} minutes and can only be used once.\n\n"
        f"If you did not request a password reset, you can safely ignore this email.\n"
        f"Your account credentials remain secure and unchanged.\n\n"
        f"--\n"
        f"Athenaeum Academic Intelligence Platform\n"
        f"University Smart Library Systems\n"
    )


def build_password_reset_html(recipient_name: str, reset_url: str, expire_minutes: int) -> str:
    """Builds a styled, responsive HTML password reset email."""
    name = recipient_name.strip() if recipient_name else "Scholar"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Reset Your Athenaeum Password</title>
  <style>
    body {{
      margin: 0;
      padding: 0;
      background-color: #0c1017;
      color: #e2e8f0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      line-height: 1.6;
    }}
    .email-wrapper {{
      max-width: 580px;
      margin: 2rem auto;
      background-color: #161e2e;
      border: 1px solid #283548;
      border-radius: 8px;
      overflow: hidden;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
    }}
    .email-header {{
      background: linear-gradient(135deg, #0d1527 0%, #1a263d 100%);
      padding: 1.75rem 2rem;
      border-bottom: 1px solid #283548;
      text-align: center;
    }}
    .platform-title {{
      font-size: 1.25rem;
      font-weight: 700;
      letter-spacing: 0.05em;
      color: #38bdf8;
      margin: 0;
    }}
    .platform-subtitle {{
      font-size: 0.8rem;
      color: #94a3b8;
      margin-top: 0.25rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .email-body {{
      padding: 2rem;
    }}
    h1 {{
      font-size: 1.25rem;
      color: #f8fafc;
      margin-top: 0;
      margin-bottom: 1rem;
    }}
    p {{
      color: #cbd5e1;
      font-size: 0.95rem;
      margin-bottom: 1.25rem;
    }}
    .cta-container {{
      text-align: center;
      margin: 2rem 0;
    }}
    .btn-reset {{
      display: inline-block;
      background-color: #0284c7;
      color: #ffffff !important;
      font-weight: 600;
      font-size: 0.95rem;
      text-decoration: none;
      padding: 0.75rem 2rem;
      border-radius: 6px;
      letter-spacing: 0.02em;
    }}
    .alt-link {{
      background-color: #0f172a;
      padding: 0.75rem;
      border-radius: 4px;
      border: 1px solid #1e293b;
      word-break: break-all;
      font-size: 0.8rem;
      color: #38bdf8;
      font-family: monospace;
    }}
    .security-notice {{
      margin-top: 2rem;
      padding-top: 1.25rem;
      border-top: 1px solid #283548;
      font-size: 0.82rem;
      color: #94a3b8;
    }}
    .email-footer {{
      background-color: #0f172a;
      padding: 1.25rem 2rem;
      text-align: center;
      font-size: 0.78rem;
      color: #64748b;
      border-top: 1px solid #1e293b;
    }}
  </style>
</head>
<body>
  <div class="email-wrapper">
    <div class="email-header">
      <div class="platform-title">🏛️ ATHENAEUM</div>
      <div class="platform-subtitle">Academic Intelligence Platform</div>
    </div>
    <div class="email-body">
      <h1>Password Recovery Request</h1>
      <p>Hello <strong>{name}</strong>,</p>
      <p>A password reset was requested for your Athenaeum Academic Library account. Click the button below to establish a new password:</p>
      
      <div class="cta-container">
        <a href="{reset_url}" class="btn-reset" target="_blank" rel="noopener noreferrer">Reset My Password</a>
      </div>

      <p style="font-size: 0.85rem; color: #94a3b8;">If the button does not work, copy and paste this link into your browser:</p>
      <div class="alt-link">{reset_url}</div>

      <div class="security-notice">
        <p style="margin: 0 0 0.5rem 0;"><strong>Security Notice:</strong></p>
        <ul style="margin: 0; padding-left: 1.25rem;">
          <li>This link is valid for <strong>{expire_minutes} minutes</strong> and can only be used once.</li>
          <li>If you did not request this change, you can safely ignore this email.</li>
          <li>Athenaeum librarians and system administrators will never ask for your password.</li>
        </ul>
      </div>
    </div>
    <div class="email-footer">
      This is an automated administrative notification from Athenaeum Smart Library Systems.<br>
      Please do not reply directly to this email.
    </div>
  </div>
</body>
</html>"""


class EmailService:
    """
    Production-conscious SMTP email service.
    Handles message composition, TLS/SSL negotiation, and graceful failure.
    """

    def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str,
    ) -> bool:
        """
        Sends an email via configured SMTP server.
        Returns True if delivery succeeded, False if email is disabled or failed.
        Never logs passwords or full reset tokens.
        """
        settings = get_settings()

        if not settings.EMAIL_ENABLED:
            logger.info(
                "Transactional email delivery is disabled (EMAIL_ENABLED=False). Message to %s was not sent.",
                obfuscate_email(to_email),
            )
            return False

        # Validate minimum delivery parameters
        if not settings.SMTP_HOST or not settings.SMTP_FROM_EMAIL:
            logger.error("SMTP delivery aborted: SMTP_HOST or SMTP_FROM_EMAIL is not configured.")
            return False

        # Build MIME alternative message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = Header(subject, "utf-8")
        msg["From"] = formataddr((str(Header(settings.SMTP_FROM_NAME, "utf-8")), settings.SMTP_FROM_EMAIL))
        msg["To"] = to_email

        # Attach text and html parts (text first, html second per RFC standard)
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        timeout = float(settings.SMTP_TIMEOUT_SECONDS)

        try:
            if settings.SMTP_PORT == 465:
                # SSL Direct Connection
                with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=timeout) as server:
                    if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                    server.send_message(msg)
            else:
                # Standard connection with STARTTLS
                with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=timeout) as server:
                    server.ehlo()
                    if settings.SMTP_USE_TLS:
                        server.starttls()
                        server.ehlo()
                    if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                    server.send_message(msg)

            logger.info("Successfully delivered email '%s' to %s", subject, obfuscate_email(to_email))
            return True

        except smtplib.SMTPAuthenticationError as exc:
            logger.error("SMTP authentication failure connecting to %s:%s", settings.SMTP_HOST, settings.SMTP_PORT)
            return False
        except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected) as exc:
            logger.error("SMTP connection failure to %s:%s: %s", settings.SMTP_HOST, settings.SMTP_PORT, type(exc).__name__)
            return False
        except TimeoutError as exc:
            logger.error("SMTP timeout connecting to %s:%s after %.1fs", settings.SMTP_HOST, settings.SMTP_PORT, timeout)
            return False
        except Exception as exc:
            logger.error("Unexpected failure delivering transactional email via SMTP: %s", type(exc).__name__)
            return False

    def send_password_reset_email(
        self,
        to_email: str,
        recipient_name: str,
        reset_token: str,
    ) -> bool:
        """
        Composes and delivers the secure password-reset notification.
        Constructs the reset link and dispatches both HTML and plain-text templates.
        """
        settings = get_settings()

        # Construct frontend recovery URL
        base_url = settings.FRONTEND_BASE_URL.rstrip("/")
        reset_url = f"{base_url}/?reset_token={reset_token}"

        subject = "Reset Your Athenaeum Password"
        expire_minutes = int(settings.RESET_TOKEN_EXPIRE_MINUTES)

        text_body = build_password_reset_text(recipient_name, reset_url, expire_minutes)
        html_body = build_password_reset_html(recipient_name, reset_url, expire_minutes)

        return self.send_email(
            to_email=to_email,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
        )


# Global singleton instance
email_service = EmailService()

