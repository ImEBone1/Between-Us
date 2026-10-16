from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


MOODS = [
    ("love", "I'm Feeling Love", "💗", "rose"),
    ("missing", "I'm Missing You", "🥺", "lilac"),
    ("sad", "I'm Feeling Sad", "🌧️", "sky"),
    ("hug", "I Need a Hug", "🫂", "peach"),
    ("happy", "I'm Happy", "✨", "sun"),
    ("space", "I Need Some Space", "🌙", "lavender"),
    ("thinking", "I'm Thinking of You", "💭", "mint"),
    ("support", "I Need Your Support", "🤍", "cloud"),
]
MOOD_MAP = {key: {"label": label, "emoji": emoji, "tone": tone} for key, label, emoji, tone in MOODS}

REACTIONS = [
    ("love", "Send Love", "💞"),
    ("hug", "Send a Hug", "🫂"),
    ("here", "I'm Here for You", "🤍"),
    ("kiss", "Sending a Kiss", "💋"),
    ("happy", "You Make Me Happy", "✨"),
]
REACTION_MAP = {key: {"label": label, "emoji": emoji} for key, label, emoji in REACTIONS}


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    display_name = models.CharField(max_length=80, blank=True)
    avatar_color = models.CharField(max_length=20, default="rose")
    notifications_enabled = models.BooleanField(default=True)
    do_not_disturb = models.BooleanField(default=False)
    browser_notifications_enabled = models.BooleanField(default=True)
    vibration_enabled = models.BooleanField(default=True)
    sound_enabled = models.BooleanField(default=True)
    mood_expiration_hours = models.PositiveIntegerField(default=12)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["user__username"]

    def __str__(self):
        return self.display_name or self.user.get_username()

    @property
    def name(self):
        return self.display_name.strip() or self.user.get_username()

    @property
    def initials(self):
        words = self.name.split()
        if len(words) >= 2:
            return (words[0][0] + words[1][0]).upper()
        return self.name[:2].upper()


class CoupleConnection(models.Model):
    PENDING = "pending"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    STATUS_CHOICES = [(PENDING, "Pending"), (CONNECTED, "Connected"), (DISCONNECTED, "Disconnected")]

    inviter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_connections")
    invitee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name="received_connections")
    code = models.CharField(max_length=32, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    connected_at = models.DateTimeField(null=True, blank=True)
    disconnected_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "expires_at"])]

    def clean(self):
        if self.invitee_id and self.inviter_id == self.invitee_id:
            raise ValidationError("You cannot connect with yourself.")

    @property
    def is_active(self):
        return self.status == self.CONNECTED

    @property
    def is_expired(self):
        return self.status == self.PENDING and timezone.now() >= self.expires_at

    def partner_for(self, user):
        if user.pk == self.inviter_id:
            return self.invitee
        if self.invitee_id and user.pk == self.invitee_id:
            return self.inviter
        return None


class Mood(models.Model):
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="moods")
    connection = models.ForeignKey(CoupleConnection, on_delete=models.CASCADE, related_name="moods")
    mood_type = models.CharField(max_length=20, choices=[(key, label) for key, label, _, _ in MOODS])
    message = models.CharField(max_length=160, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["connection", "sender", "-created_at"])]

    def clean(self):
        if not self.connection or not self.connection.is_active:
            raise ValidationError("A mood requires an active connection.")
        if self.sender_id not in {self.connection.inviter_id, self.connection.invitee_id}:
            raise ValidationError("You are not part of this connection.")

    @property
    def mood(self):
        return MOOD_MAP[self.mood_type]

    @property
    def is_active(self):
        return timezone.now() < self.expires_at

    @property
    def label(self):
        return self.mood["label"]

    @property
    def emoji(self):
        return self.mood["emoji"]

    @property
    def tone(self):
        return self.mood["tone"]


class MoodReaction(models.Model):
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_reactions")
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="received_reactions")
    connection = models.ForeignKey(CoupleConnection, on_delete=models.CASCADE, related_name="reactions")
    mood = models.ForeignKey(Mood, on_delete=models.SET_NULL, null=True, blank=True, related_name="reactions")
    reaction_type = models.CharField(max_length=20, choices=[(key, label) for key, label, _ in REACTIONS])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["connection", "-created_at"])]

    @property
    def reaction(self):
        return REACTION_MAP[self.reaction_type]


class Notification(models.Model):
    MOOD = "mood"
    REACTION = "reaction"
    TYPE_CHOICES = [(MOOD, "Mood"), (REACTION, "Reaction")]

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    connection = models.ForeignKey(CoupleConnection, on_delete=models.CASCADE, related_name="notifications")
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    mood = models.ForeignKey(Mood, on_delete=models.CASCADE, null=True, blank=True, related_name="notifications")
    reaction = models.ForeignKey(MoodReaction, on_delete=models.CASCADE, null=True, blank=True, related_name="notifications")
    title = models.CharField(max_length=120)
    body = models.CharField(max_length=240)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["recipient", "-created_at"]), models.Index(fields=["recipient", "read_at"])]

    @property
    def is_read(self):
        return self.read_at is not None


class PushSubscription(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="push_subscriptions")
    endpoint = models.URLField(max_length=2048, unique=True)
    p256dh = models.CharField(max_length=255)
    auth = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [models.Index(fields=["user", "-updated_at"])]


