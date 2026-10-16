from django.contrib.auth.views import LogoutView
from django.urls import path

from .views import (
    BetweenUsLoginView,
    api_mood,
    api_reaction,
    connect,
    dashboard,
    disconnect,
    home,
    moments,
    notifications,
    read,
    register,
    settings_page,
)

urlpatterns = [
    path("", home, name="home"),
    path("accounts/register/", register, name="register"),
    path("accounts/login/", BetweenUsLoginView.as_view(), name="login"),
    path("accounts/logout/", LogoutView.as_view(), name="logout"),
    path("dashboard/", dashboard, name="dashboard"),
    path("connect/", connect, name="connect"),
    path("connect/disconnect/", disconnect, name="disconnect"),
    path("moments/", moments, name="moments"),
    path("settings/", settings_page, name="settings"),
    path("notifications/", notifications, name="notifications"),
    path("notifications/<int:pk>/read/", read, name="read_notification"),
    path("api/moods/", api_mood, name="api_mood"),
    path("api/reactions/", api_reaction, name="api_reaction"),
]

