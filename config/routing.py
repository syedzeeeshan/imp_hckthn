"""
WebSocket URL routing for Campus Club Management Suite
"""
from django.urls import re_path
from apps.notifications.consumers import NotificationConsumer
from apps.messaging.consumers import MessagingConsumer
from apps.events.consumers import EventConsumer

websocket_urlpatterns = [
    re_path(r'ws/notifications/(?P<user_id>\w+)/$', NotificationConsumer.as_asgi()),
    re_path(r'ws/messaging/(?P<room_name>\w+)/$', MessagingConsumer.as_asgi()),
    re_path(r'ws/events/(?P<event_id>\w+)/$', EventConsumer.as_asgi()),
]
