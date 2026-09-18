from django.urls import re_path
from notifications.views import (
    NotificationListView,
    NotificationMarkAsReadView,
    NotificationMarkAllAsReadView,
    NotificationUnreadCountView,
    NotificationResolveActionView,
    NotificationDeleteView,
    NotificationPreferenceView,
    DevicePushTokenView,
)

urlpatterns = [
    re_path(r'^notifications/?$', NotificationListView.as_view(), name='notification_list'),
    re_path(r'^notifications/unread-count/?$', NotificationUnreadCountView.as_view(), name='notification_unread_count'),
    re_path(r'^notifications/read-all/?$', NotificationMarkAllAsReadView.as_view(), name='notification_mark_all_as_read'),
    re_path(r'^notifications/mark-all-read/?$', NotificationMarkAllAsReadView.as_view(), name='notification_mark_all_as_read_alias'),
    re_path(r'^notifications/preferences/?$', NotificationPreferenceView.as_view(), name='notification_preferences'),
    re_path(r'^notifications/devices/?$', DevicePushTokenView.as_view(), name='notification_devices'),
    re_path(r'^notifications/(?P<notification_id>[0-9a-fA-F-]+)/read/?$', NotificationMarkAsReadView.as_view(), name='notification_mark_as_read'),
    re_path(r'^notifications/(?P<notification_id>[0-9a-fA-F-]+)/resolve-action/?$', NotificationResolveActionView.as_view(), name='notification_resolve_action'),
    re_path(r'^notifications/(?P<notification_id>[0-9a-fA-F-]+)/?$', NotificationDeleteView.as_view(), name='notification_delete'),
]
