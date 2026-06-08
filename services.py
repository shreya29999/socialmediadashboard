# ================================================================
# SECTION 1 — IMPORTS
# ================================================================

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import os

load_dotenv()

SMTP_HOST     = os.getenv("SMTP_HOST")
SMTP_PORT     = int(os.getenv("SMTP_PORT", 587))
SMTP_EMAIL    = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM     = os.getenv("SMTP_FROM_NAME", "Social Dashboard")


# ================================================================
# SECTION 2 — BASE EMAIL SENDER
# ================================================================

def send_email(to_email: str, subject: str, html_body: str):
    
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"{SMTP_FROM} <{SMTP_EMAIL}>"
        msg["To"]      = to_email

        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, to_email, msg.as_string())

        print(f"✅ Email sent to {to_email}")
        return True

    except Exception as e:
        print(f"❌ Email failed: {e}")
        return False


# ================================================================
# SECTION 3 — CONFIRMATION EMAIL (Approve / Reject)
# ================================================================

def send_confirmation_email(
    to_email: str,
    post_content: str,
    platforms: list,
    scheduled_at: str,
    approve_url: str,
    reject_url: str
):
    
    platforms_text = " + ".join([p.upper() for p in platforms])

    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto;">

        <h2 style="color: #2c3e50;">⏰ Your post is ready to go live</h2>

        <p>Your scheduled post needs your approval before publishing:</p>

        <div style="background: #f4f4f4; padding: 15px; border-radius: 8px; margin: 20px 0;">
            <p><strong>📝 Content:</strong> {post_content}</p>
            <p><strong>📱 Platforms:</strong> {platforms_text}</p>
            <p><strong>🕐 Scheduled:</strong> {scheduled_at}</p>
        </div>

        <p>Click below to approve or cancel this post:</p>

        <div style="margin: 30px 0;">
            <a href="{approve_url}"
               style="background: #27ae60; color: white; padding: 12px 24px;
                      text-decoration: none; border-radius: 6px; margin-right: 15px;">
               ✅ APPROVE & PUBLISH
            </a>

            <a href="{reject_url}"
               style="background: #e74c3c; color: white; padding: 12px 24px;
                      text-decoration: none; border-radius: 6px;">
               ❌ CANCEL POST
            </a>
        </div>

        <p style="color: #e74c3c; font-size: 13px;">
            ⚠️ This confirmation expires at scheduled time.
            If no action is taken, post will be automatically cancelled.
        </p>

    </div>
    """

    return send_email(
        to_email=to_email,
        subject=f"✅ Confirm your post for {scheduled_at}",
        html_body=html_body
    )


# ================================================================
# SECTION 4 — SUCCESS EMAIL
# ================================================================

def send_success_email(
    to_email: str,
    post_content: str,
    platforms: list,
    published_at: str
):
    
    platforms_text = " + ".join([p.upper() for p in platforms])

    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto;">

        <h2 style="color: #27ae60;">✅ Your post is live!</h2>

        <div style="background: #f4f4f4; padding: 15px; border-radius: 8px; margin: 20px 0;">
            <p><strong>📝 Content:</strong> {post_content}</p>
            <p><strong>📱 Published on:</strong> {platforms_text}</p>
            <p><strong>🕐 Published at:</strong> {published_at}</p>
        </div>

        <p>Your post has been successfully published. Check your social accounts to see it live.</p>

    </div>
    """

    return send_email(
        to_email=to_email,
        subject="✅ Your post is now live!",
        html_body=html_body
    )


# ================================================================
# SECTION 5 — FAILURE EMAIL
# ================================================================

def send_failure_email(
    to_email: str,
    post_content: str,
    failed_platforms: list,
    error: str
):
    
    platforms_text = " + ".join([p.upper() for p in failed_platforms])

    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto;">

        <h2 style="color: #e74c3c;">❌ Post publishing failed</h2>

        <div style="background: #f4f4f4; padding: 15px; border-radius: 8px; margin: 20px 0;">
            <p><strong>📝 Content:</strong> {post_content}</p>
            <p><strong>📱 Failed on:</strong> {platforms_text}</p>
            <p><strong>⚠️ Reason:</strong> {error}</p>
        </div>

        <p>Please check your connected accounts and try again from your dashboard.</p>

    </div>
    """

    return send_email(
        to_email=to_email,
        subject="❌ Your post failed to publish",
        html_body=html_body
    )


# ================================================================
# SECTION 6 — EXPIRED EMAIL
# ================================================================

def send_expired_email(
    to_email: str,
    post_content: str,
    scheduled_at: str
):
    
    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto;">

        <h2 style="color: #e67e22;">⚠️ Post expired without approval</h2>

        <div style="background: #f4f4f4; padding: 15px; border-radius: 8px; margin: 20px 0;">
            <p><strong>📝 Content:</strong> {post_content}</p>
            <p><strong>🕐 Was scheduled for:</strong> {scheduled_at}</p>
        </div>

        <p>This post was not approved in time and has been cancelled.</p>
        <p>You can reschedule it from your dashboard.</p>

    </div>
    """

    return send_email(
        to_email=to_email,
        subject="⚠️ Your scheduled post expired",
        html_body=html_body
    )