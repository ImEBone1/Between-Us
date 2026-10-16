from django.contrib import admin

from .models import CoupleConnection, Mood, MoodReaction, Notification, Profile, PushSubscription


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "display_name", "notifications_enabled", "do_not_disturb")
    search_fields = ("user__username", "display_name")


@admin.register(CoupleConnection)
class CoupleConnectionAdmin(admin.ModelAdmin):
    list_display = ("inviter", "invitee", "status", "created_at", "expires_at")
    list_filter = ("status",)
    search_fields = ("inviter__username", "invitee__username", "code")


@admin.register(Mood)
class MoodAdmin(admin.ModelAdmin):
    list_display = ("sender", "mood_type", "connection", "created_at", "expires_at")
    list_filter = ("mood_type",)


@admin.register(MoodReaction)
class MoodReactionAdmin(admin.ModelAdmin):
    list_display = ("sender", "recipient", "reaction_type", "created_at")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("recipient", "notification_type", "title", "created_at", "read_at")
    list_filter = ("notification_type", "read_at")


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "endpoint", "updated_at")
    search_fields = ("user__username", "endpoint")

