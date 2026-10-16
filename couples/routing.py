from django.urls import path

from .consumers import CoupleConsumer

websocket_urlpatterns = [path("ws/couple/", CoupleConsumer.as_asgi())]

