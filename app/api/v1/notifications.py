from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_current_user
from app.repositories.notification_repository import (
    delete_notification,
    get_notifications,
    get_unread_notification_count,
    mark_all_notifications_read,
    mark_notification_read,
)


router = APIRouter(
    tags=["Notifications"],
)


@router.get("/notifications")
def list_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(50, le=200),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]

    notifications = get_notifications(
        user_id,
        unread_only=unread_only,
        limit=limit,
    )

    unread_count = get_unread_notification_count(user_id)

    return {
        "notifications": notifications or [],
        "total": len(notifications) if notifications else 0,
        "unread_count": unread_count,
    }


@router.get("/notifications/unread-count")
def notifications_unread_count(
    current_user: dict = Depends(get_current_user),
):
    return {
        "unread_count": get_unread_notification_count(
            current_user["user_id"]
        )
    }


@router.patch("/notifications/{notification_id}/read")
def read_notification(
    notification_id: int,
    current_user: dict = Depends(get_current_user),
):
    mark_notification_read(
        notification_id,
        current_user["user_id"],
    )

    return {
        "message": "Notification marked as read ✅",
    }


@router.patch("/notifications/read-all")
def read_all_notifications(
    current_user: dict = Depends(get_current_user),
):
    mark_all_notifications_read(
        current_user["user_id"]
    )

    return {
        "message": "All notifications marked as read ✅",
    }


@router.delete("/notifications/{notification_id}")
def remove_notification(
    notification_id: int,
    current_user: dict = Depends(get_current_user),
):
    delete_notification(
        notification_id,
        current_user["user_id"],
    )

    return {
        "message": "Notification deleted ✅",
    }