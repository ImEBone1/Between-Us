import json
import logging
import secrets
from datetime import timedelta

from asgiref.sync import async_to_sync
from django.conf import settings
from channels.layers import get_channel_layer
from django.utils import timezone

from .models import CoupleConnection, Mood, MoodReaction, Notification, PushSubscription, MOOD_MAP, REACTION_MAP

try:
    from pywebpush import WebPushException, webpush
except ImportError:  # pragma: no cover - requirements.txt installs this in normal environments
    WebPushException = Exception
    webpush = None

logger = logging.getLogger(__name__)


def profile_for(user):
    return user.profile


def connection_for(user):
    if not user or not user.is_authenticated:
        return None
    return CoupleConnection.objects.filter(status=CoupleConnection.CONNECTED, inviter=user).first() or CoupleConnection.objects.filter(status=CoupleConnection.CONNECTED, invitee=user).first()


def invite_for(user):
    pending = CoupleConnection.objects.filter(inviter=user, status=CoupleConnection.PENDING).order_by("-created_at").first()
    if pending and not pending.is_expired:
        return pending
    if pending:
        pending.status = CoupleConnection.DISCONNECTED
        pending.save(update_fields=["status"])
    return CoupleConnection.objects.create(inviter=user, code=secrets.token_urlsafe(12), expires_at=timezone.now() + timedelta(days=7))


def connect_with_code(user, code):
    code = (code or "").strip()
    if not code:
        return None, "Enter an invitation code."
    try:
        connection = CoupleConnection.objects.select_for_update().get(code=code, status=CoupleConnection.PENDING)
    except CoupleConnection.DoesNotExist:
        return None, "That invitation is no longer valid. Ask your person for a fresh code."
    if connection.is_expired:
        connection.status = CoupleConnection.DISCONNECTED
        connection.save(update_fields=["status"])
        return None, "That invitation has expired. Ask your person for a fresh code."
    if connection.inviter_id == user.id:
        return None, "You cannot accept your own invitation."
    if connection_for(user):
        return None, "You are already connected to someone. Disconnect first to start over."
    if CoupleConnection.objects.filter(status=CoupleConnection.CONNECTED, inviter=connection.inviter).exists():
        return None, "That invitation is already connected."
    connection.invitee = user
    connection.status = CoupleConnection.CONNECTED
    connection.connected_at = timezone.now()
    connection.save(update_fields=["invitee", "status", "connected_at"])
    return connection, None


def send_group_event(connection, event_type, payload):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(f"couple_{connection.pk}", {"type": event_type, **payload})


def send_web_push(user, payload):
    profile = profile_for(user)
    if (
        webpush is None
        or not settings.VAPID_PUBLIC_KEY
        or not settings.VAPID_PRIVATE_KEY
        or not profile.notifications_enabled
        or not profile.browser_notifications_enabled
        or profile.do_not_disturb
    ):
        return
    subscriptions = list(PushSubscription.objects.filter(user=user))
    for subscription in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": subscription.endpoint,
                    "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
                },
                data=json.dumps(payload),
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims={"sub": settings.VAPID_CLAIMS_EMAIL},
            )
        except WebPushException as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            if status_code in {404, 410}:
                subscription.delete()
            else:
                logger.warning("Browser push failed for user %s: %s", user.pk, exc)
        except Exception:
            logger.exception("Unexpected browser push failure for user %s", user.pk)


def create_mood(user, mood_type):
    connection = connection_for(user)
    if not connection:
        return None, "Connect with your person before sharing a mood."
    if mood_type not in MOOD_MAP:
        return None, "Choose one of the available moods."
    now = timezone.now()
    duplicate = Mood.objects.filter(sender=user, mood_type=mood_type, created_at__gte=now - timedelta(seconds=3)).first()
    if duplicate:
        return duplicate, None
    expires_at = now + timedelta(hours=profile_for(user).mood_expiration_hours)
    mood = Mood.objects.create(sender=user, connection=connection, mood_type=mood_type, expires_at=expires_at)
    partner = connection.partner_for(user)
    partner_profile = profile_for(partner)
    notification = None
    if partner_profile.notifications_enabled and not partner_profile.do_not_disturb:
        notification = Notification.objects.create(
            recipient=partner,
            connection=connection,
            notification_type=Notification.MOOD,
            mood=mood,
            title=f"{profile_for(user).name} shared a feeling",
            body=f"{profile_for(user).name} {mood.label.lower()} {mood.emoji}",
        )
    send_web_push(partner, {
        "title": f"{profile_for(user).name} shared a feeling",
        "body": f"{profile_for(user).name} {mood.label.lower()} {mood.emoji}",
        "mood_type": mood_type,
        "sound": mood_type,
        "sound_enabled": partner_profile.sound_enabled,
        "vibration_enabled": partner_profile.vibration_enabled,
        "url": "/dashboard/",
    })
    send_group_event(connection, "mood_event", {"sender_id": user.id, "mood_id": mood.id, "mood_type": mood_type})
    return mood, None


def create_reaction(user, reaction_type, mood_id=None):
    connection = connection_for(user)
    if not connection:
        return None, "Connect with your person before sending a reaction."
    if reaction_type not in REACTION_MAP:
        return None, "Choose one of the available reactions."
    partner = connection.partner_for(user)
    mood = Mood.objects.filter(pk=mood_id, connection=connection).first() if mood_id else None
    reaction = MoodReaction.objects.create(sender=user, recipient=partner, connection=connection, mood=mood, reaction_type=reaction_type)
    partner_profile = profile_for(partner)
    notification = None
    if partner_profile.notifications_enabled and not partner_profile.do_not_disturb:
        notification = Notification.objects.create(
            recipient=partner,
            connection=connection,
            notification_type=Notification.REACTION,
            reaction=reaction,
            title=f"{profile_for(user).name} sent a little something",
            body=f"{REACTION_MAP[reaction_type]['label']} {REACTION_MAP[reaction_type]['emoji']}",
        )
    send_web_push(partner, {
        "title": f"{profile_for(user).name} sent a little something",
        "body": f"{REACTION_MAP[reaction_type]['label']} {REACTION_MAP[reaction_type]['emoji']}",
        "sound": reaction_type,
        "sound_enabled": partner_profile.sound_enabled,
        "vibration_enabled": partner_profile.vibration_enabled,
        "url": "/dashboard/",
    })
    send_group_event(connection, "reaction_event", {"sender_id": user.id, "reaction_id": reaction.id, "reaction_type": reaction_type})
    return reaction, None


def mark_read(user, notification_id):
    return Notification.objects.filter(pk=notification_id, recipient=user, read_at__isnull=True).update(read_at=timezone.now())

