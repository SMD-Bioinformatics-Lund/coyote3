"""Recipient-scoped notification and administrative broadcast routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api.app.container import util
from api.app.deps.application import get_notifications
from api.interfaces.http.tags import TAG_NOTIFICATIONS
from api.security.access import ApiUser, require_access
from coyote3.application.operations.notifications import Notifications
from coyote3.contracts.notifications import (
    NotificationBroadcastRequest,
    NotificationBroadcastResponse,
    NotificationChangePayload,
    NotificationListPayload,
    NotificationRecipientsPayload,
)

router = APIRouter(tags=[TAG_NOTIFICATIONS])


@router.get(
    "/api/v1/notifications",
    response_model=NotificationListPayload,
    include_in_schema=False,
)
def notification_inbox(
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: ApiUser = Depends(require_access()),
    service: Notifications = Depends(get_notifications),
):
    """Return only notifications visible to the authenticated user."""
    return util.common.convert_to_serializable(service.inbox(limit=limit, offset=offset))


@router.patch(
    "/api/v1/notifications/read-all",
    response_model=NotificationChangePayload,
    include_in_schema=False,
)
def notification_mark_all_read(
    user: ApiUser = Depends(require_access()),
    service: Notifications = Depends(get_notifications),
):
    """Mark every visible notification as read for the authenticated user."""
    return util.common.convert_to_serializable(service.mark_all_read())


@router.patch(
    "/api/v1/notifications/{notification_id}/read",
    response_model=NotificationChangePayload,
    include_in_schema=False,
)
def notification_mark_read(
    notification_id: str,
    user: ApiUser = Depends(require_access()),
    service: Notifications = Depends(get_notifications),
):
    """Mark one visible notification as read for the authenticated user."""
    return util.common.convert_to_serializable(service.mark_read(notification_id=notification_id))


@router.patch(
    "/api/v1/notifications/{notification_id}/unread",
    response_model=NotificationChangePayload,
    include_in_schema=False,
)
def notification_mark_unread(
    notification_id: str,
    user: ApiUser = Depends(require_access()),
    service: Notifications = Depends(get_notifications),
):
    """Mark one visible notification unread for the authenticated recipient."""
    return util.common.convert_to_serializable(service.mark_unread(notification_id=notification_id))


@router.delete(
    "/api/v1/notifications",
    response_model=NotificationChangePayload,
    include_in_schema=False,
)
def notification_dismiss_all(
    user: ApiUser = Depends(require_access()),
    service: Notifications = Depends(get_notifications),
):
    """Dismiss every visible notification for the authenticated user."""
    return util.common.convert_to_serializable(service.dismiss_all())


@router.delete(
    "/api/v1/notifications/{notification_id}",
    response_model=NotificationChangePayload,
    include_in_schema=False,
)
def notification_dismiss(
    notification_id: str,
    user: ApiUser = Depends(require_access()),
    service: Notifications = Depends(get_notifications),
):
    """Clear a personal notification, or withdraw a sender-owned broadcast for everyone."""
    return util.common.convert_to_serializable(service.dismiss(notification_id=notification_id))


@router.get("/api/v1/admin/notifications/sent", response_model=NotificationListPayload)
def notification_sent(
    user: ApiUser = Depends(require_access(permission="notification.broadcast:create")),
    service: Notifications = Depends(get_notifications),
):
    """List the authenticated sender's broadcasts, including their expiry and withdrawal state."""
    return util.common.convert_to_serializable(service.sent())


@router.get(
    "/api/v1/admin/notifications/recipients",
    response_model=NotificationRecipientsPayload,
    include_in_schema=False,
)
def notification_recipient_options(
    user: ApiUser = Depends(require_access(permission="notification.broadcast:create")),
    service: Notifications = Depends(get_notifications),
):
    """Return active accounts and populated roles available for broadcasts."""
    return util.common.convert_to_serializable(service.recipient_options())


@router.post(
    "/api/v1/admin/notifications/broadcast",
    response_model=NotificationBroadcastResponse,
)
def notification_broadcast(
    payload: NotificationBroadcastRequest,
    user: ApiUser = Depends(require_access(permission="notification.broadcast:create")),
    service: Notifications = Depends(get_notifications),
):
    """Publish an application message to all, role-matched, or selected active users."""
    return util.common.convert_to_serializable(service.broadcast(payload=payload))
