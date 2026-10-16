from django.contrib.auth.views import LogoutView
from django.urls import path

from .views import (
    BetweenUsLoginView,
    api_mood,
    api_reaction,
    connect,
    dashboard,
    dashboard_state,
    disconnect,
    home,
    moments,
    notifications,
    push_subscribe,
    push_unsubscribe,
    read,
    register,
    service_worker,
    settings_page,
)

urlpatterns = [
    path("", home, name="home"),
    path("sw.js", service_worker, name="service_worker"),
    path("accounts/register/", register, name="register"),
    path("accounts/login/", BetweenUsLoginView.as_view(), name="login"),
    path("accounts/logout/", LogoutView.as_view(), name="logout"),
    path("dashboard/", dashboard, name="dashboard"),
    path("api/dashboard-state/", dashboard_state, name="dashboard_state"),
    path("connect/", connect, name="connect"),
    path("connect/disconnect/", disconnect, name="disconnect"),
    path("moments/", moments, name="moments"),
    path("settings/", settings_page, name="settings"),
    path("notifications/", notifications, name="notifications"),
    path("notifications/<int:pk>/read/", read, name="read_notification"),
    path("api/moods/", api_mood, name="api_mood"),
    path("api/reactions/", api_reaction, name="api_reaction"),
    path("api/push/subscribe/", push_subscribe, name="push_subscribe"),
    path("api/push/unsubscribe/", push_unsubscribe, name="push_unsubscribe"),
]

