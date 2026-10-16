import json
import time
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import ProfileForm, RegisterForm
from .models import CoupleConnection, Mood, MoodReaction, Notification, PushSubscription, MOODS, REACTIONS
from .services import connection_for, connect_with_code, create_mood, create_reaction, invite_for, mark_read


def home(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "landing.html")


def service_worker(request):
    worker_path = Path(settings.BASE_DIR) / "static" / "js" / "sw.js"
    response = HttpResponse(worker_path.read_text(encoding="utf-8"), content_type="application/javascript")
    response["Cache-Control"] = "no-cache"
    return response


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Welcome to BetweenUs. Let’s make your little corner of the internet.")
        return redirect("connect")
    return render(request, "registration/register.html", {"form": form})


class BetweenUsLoginView(LoginView):
    template_name = "registration/login.html"
    redirect_authenticated_user = True


def dashboard_view(request):
    connection = connection_for(request.user)
    if not connection:
        return redirect("connect")
    partner = connection.partner_for(request.user)
    now = timezone.now()
    own_mood = Mood.objects.filter(connection=connection, sender=request.user, expires_at__gt=now).first()
    partner_mood = Mood.objects.filter(connection=connection, sender=partner, expires_at__gt=now).first()
    latest_notifications = Notification.objects.filter(recipient=request.user, connection=connection).select_related("mood", "reaction")[:4]
    context = {
        "connection": connection,
        "partner": partner,
        "own_mood": own_mood,
        "partner_mood": partner_mood,
        "moods": [{"key": key, "label": label, "emoji": emoji, "tone": tone} for key, label, emoji, tone in MOODS],
        "reactions": [{"key": key, "label": label, "emoji": emoji} for key, label, emoji in REACTIONS],
        "latest_notifications": latest_notifications,
        "unread_count": Notification.objects.filter(recipient=request.user, read_at__isnull=True).count(),
    }
    return render(request, "dashboard.html", context)


def dashboard_state_view(request):
    connection = connection_for(request.user)
    if not connection:
        return JsonResponse({"ok": False, "error": "No active connection."}, status=400)
    partner = connection.partner_for(request.user)
    partner_mood = Mood.objects.filter(connection=connection, sender=partner, expires_at__gt=timezone.now()).first()
    latest_note = Notification.objects.filter(recipient=request.user, connection=connection).first()
    payload = {
        "ok": True,
        "partner_mood": None,
        "latest_notification_id": latest_note.id if latest_note else None,
    }
    if partner_mood:
        payload["partner_mood"] = {
            "id": partner_mood.id,
            "type": partner_mood.mood_type,
            "label": partner_mood.label,
            "emoji": partner_mood.emoji,
        }
    return JsonResponse(payload)


def connect_view(request):
    connection = connection_for(request.user)
    pending_invite = CoupleConnection.objects.filter(inviter=request.user, status=CoupleConnection.PENDING).order_by("-created_at").first()
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create_invite":
            if connection:
                messages.info(request, "You are already connected to your person.")
            else:
                pending_invite = invite_for(request.user)
                messages.success(request, "Your private invitation is ready to share.")
        elif action == "accept_invite":
            attempts = [stamp for stamp in request.session.get("invite_attempts", []) if time.time() - stamp < 60]
            if len(attempts) >= 8:
                messages.error(request, "Too many attempts in a short time. Please wait a minute and try again.")
                error = "rate_limited"
                accepted = None
            else:
                attempts.append(time.time())
                request.session["invite_attempts"] = attempts
                accepted, error = connect_with_code(request.user, request.POST.get("code"))
            if error:
                if error != "rate_limited":
                    messages.error(request, error)
            else:
                messages.success(request, "You’re connected. The quiet little channel between you is open.")
                return redirect("dashboard")
    invite_url = None
    if pending_invite and not pending_invite.is_expired:
        invite_url = request.build_absolute_uri(reverse("connect") + f"?code={pending_invite.code}")
    return render(request, "connect.html", {"connection": connection, "pending_invite": pending_invite, "invite_url": invite_url})


def disconnect_view(request):
    connection = connection_for(request.user)
    if connection:
        connection.status = CoupleConnection.DISCONNECTED
        connection.disconnected_at = timezone.now()
        connection.save(update_fields=["status", "disconnected_at"])
        messages.success(request, "You’re disconnected. Your shared history is no longer active.")
    return redirect("connect")


def moments_view(request):
    connection = connection_for(request.user)
    if not connection:
        return redirect("connect")
    entries = list(Mood.objects.filter(connection=connection).select_related("sender"))
    paginator = Paginator(entries, 12)
    page = paginator.get_page(request.GET.get("page"))
    reactions = MoodReaction.objects.filter(connection=connection).select_related("sender", "recipient", "mood")
    reaction_by_mood = {}
    for reaction in reactions:
        if reaction.mood_id and reaction.mood_id not in reaction_by_mood:
            reaction_by_mood[reaction.mood_id] = reaction
    for entry in page.object_list:
        entry.timeline_reaction = reaction_by_mood.get(entry.id)
    return render(request, "moments.html", {"connection": connection, "page": page})


def settings_view(request):
    profile = request.user.profile
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Your preferences are saved.")
            return redirect("settings")
    else:
        form = ProfileForm(instance=profile)
    connection = connection_for(request.user)
    return render(request, "settings.html", {"form": form, "connection": connection, "partner": connection.partner_for(request.user) if connection else None})


def notifications_view(request):
    items = Notification.objects.filter(recipient=request.user).select_related("mood", "reaction", "connection")
    return render(request, "notifications.html", {"notifications": items, "connection": connection_for(request.user)})


def read_notification(request, pk):
    mark_read(request.user, pk)
    return redirect(request.POST.get("next") or "notifications")


def _json_body(request):
    try:
        return json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


def api_mood_view(request):
    payload = _json_body(request)
    mood, error = create_mood(request.user, payload.get("mood_type"))
    if error:
        return JsonResponse({"ok": False, "error": error}, status=400)
    return JsonResponse({"ok": True, "mood": {"id": mood.id, "type": mood.mood_type, "label": mood.label, "emoji": mood.emoji, "expires_at": mood.expires_at.isoformat()}})


def api_reaction_view(request):
    payload = _json_body(request)
    reaction, error = create_reaction(request.user, payload.get("reaction_type"), payload.get("mood_id"))
    if error:
        return JsonResponse({"ok": False, "error": error}, status=400)
    return JsonResponse({"ok": True, "reaction": {"id": reaction.id, "type": reaction.reaction_type, "emoji": reaction.reaction["emoji"], "label": reaction.reaction["label"]}})


def push_subscribe_view(request):
    payload = _json_body(request)
    subscription = payload.get("subscription", payload)
    endpoint = subscription.get("endpoint") if isinstance(subscription, dict) else None
    keys = subscription.get("keys", {}) if isinstance(subscription, dict) else {}
    if not endpoint or not keys.get("p256dh") or not keys.get("auth"):
        return JsonResponse({"ok": False, "error": "That browser subscription is incomplete."}, status=400)
    PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={"user": request.user, "p256dh": keys["p256dh"], "auth": keys["auth"]},
    )
    return JsonResponse({"ok": True})


def push_unsubscribe_view(request):
    payload = _json_body(request)
    endpoint = payload.get("endpoint")
    if endpoint:
        PushSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()
    return JsonResponse({"ok": True})


dashboard = login_required(dashboard_view)
connect = login_required(connect_view)
disconnect = login_required(require_POST(disconnect_view))
moments = login_required(moments_view)
settings_page = login_required(settings_view)
notifications = login_required(notifications_view)
read = login_required(require_POST(read_notification))
api_mood = login_required(require_POST(api_mood_view))
api_reaction = login_required(require_POST(api_reaction_view))
dashboard_state = login_required(dashboard_state_view)
push_subscribe = login_required(require_POST(push_subscribe_view))
push_unsubscribe = login_required(require_POST(push_unsubscribe_view))

