from django.conf import settings


def betweenus_config(request):
    return {"vapid_public_key": settings.VAPID_PUBLIC_KEY}

