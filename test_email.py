from services import send_confirmation_email

send_confirmation_email(
    to_email="pushkaran194@gmail.com",
    post_content="Summer sale! 50% off today only!",
    platforms=["facebook", "instagram"],
    scheduled_at="June 10, 2025 at 9:00 AM",
    approve_url="http://localhost:8000/approvals/1/approve?token=testtoken123",
    reject_url="http://localhost:8000/approvals/1/reject?token=testtoken123"
)