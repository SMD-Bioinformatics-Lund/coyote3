"""Recipient-scoped notification and administrative broadcast routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api.app.deps.services import get_notification_service
from api.application.notifications.service import NotificationService
from api.contracts.notifications import (
    NotificationBroadcastRequest,
    NotificationBroadcastResponse,
    NotificationChangePayload,
    NotificationListPayload,
    NotificationRecipientsPayload,
)
from api.interfaces.http.tags import TAG_NOTIFICATIONS
from api.security.access import ApiUser, require_access

router = APIRouter(tags=[TAG_NOTIFICATIONS])


@router.get("/api/v1/notifications", response_model=NotificationListPayload)
def notification_inbox(
    limit: int = Query(default=200, ge=1, le=500),
    user: ApiUser = Depends(require_access()),
    service: NotificationService = Depends(get_notification_service),
):
    """Return only notifications visible to the authenticated user."""
    return service.inbox(username=user.username, limit=limit)


@router.patch("/api/v1/notifications/read-all", response_model=NotificationChangePayload)
def notification_mark_all_read(
    user: ApiUser = Depends(require_access()),
    service: NotificationService = Depends(get_notification_service),
):
    """Mark every visible notification as read for the authenticated user."""
    return service.mark_all_read(username=user.username)


@router.patch(
    "/api/v1/notifications/{notification_id}/read", response_model=NotificationChangePayload
)
def notification_mark_read(
    notification_id: str,
    user: ApiUser = Depends(require_access()),
    service: NotificationService = Depends(get_notification_service),
):
    """Mark one visible notification as read for the authenticated user."""
    return service.mark_read(notification_id=notification_id, username=user.username)


@router.delete("/api/v1/notifications", response_model=NotificationChangePayload)
def notification_dismiss_all(
    user: ApiUser = Depends(require_access()),
    service: NotificationService = Depends(get_notification_service),
):
    """Dismiss every visible notification for the authenticated user."""
    return service.dismiss_all(username=user.username)


@router.delete("/api/v1/notifications/{notification_id}", response_model=NotificationChangePayload)
def notification_dismiss(
    notification_id: str,
    user: ApiUser = Depends(require_access()),
    service: NotificationService = Depends(get_notification_service),
):
    """Dismiss one notification for the authenticated user only."""
    return service.dismiss(notification_id=notification_id, username=user.username)


@router.get(
    "/api/v1/admin/notifications/recipients",
    response_model=NotificationRecipientsPayload,
)
def notification_recipient_options(
    user: ApiUser = Depends(require_access(permission="notification.broadcast:create")),
    service: NotificationService = Depends(get_notification_service),
):
    """Return active accounts and populated roles available for broadcasts."""
    _ = user
    return service.recipient_options()


@router.post(
    "/api/v1/admin/notifications/broadcast",
    response_model=NotificationBroadcastResponse,
)
def notification_broadcast(
    payload: NotificationBroadcastRequest,
    user: ApiUser = Depends(require_access(permission="notification.broadcast:create")),
    service: NotificationService = Depends(get_notification_service),
):
    """Publish an application message to all, role-matched, or selected active users."""
    return service.broadcast(payload=payload.model_dump(), actor=user)
