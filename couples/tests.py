from datetime import timedelta

from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from config.asgi import application
from .models import CoupleConnection, Mood, MoodReaction, Notification, PushSubscription
from .services import connect_with_code, create_mood, create_reaction, invite_for


class BetweenUsFlowTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="a-strong-password-123")
        self.bob = User.objects.create_user(username="bob", password="b-strong-password-123")

    def test_registration_creates_profile_and_redirects_to_connect(self):
        response = self.client.post(reverse("register"), {"username": "carol", "password1": "c-strong-password-123", "password2": "c-strong-password-123"})
        self.assertRedirects(response, reverse("connect"))
        self.assertTrue(User.objects.filter(username="carol", profile__isnull=False).exists())

    def test_invitation_acceptance_connects_two_people_once(self):
        invite = invite_for(self.alice)
        connection, error = connect_with_code(self.bob, invite.code)
        self.assertIsNone(error)
        self.assertEqual(connection.status, CoupleConnection.CONNECTED)
        self.assertEqual(connection.partner_for(self.alice), self.bob)
        duplicate, error = connect_with_code(User.objects.create_user(username="third", password="t-strong-password-123"), invite.code)
        self.assertIsNone(duplicate)
        self.assertIn("no longer valid", error)

    def test_expired_invitation_is_rejected(self):
        invite = invite_for(self.alice)
        invite.expires_at = timezone.now() - timedelta(hours=1)
        invite.save(update_fields=["expires_at"])
        connection, error = connect_with_code(self.bob, invite.code)
        self.assertIsNone(connection)
        self.assertIn("expired", error)

    def test_moods_and_reactions_are_private_to_the_connection(self):
        invite = invite_for(self.alice)
        connection, _ = connect_with_code(self.bob, invite.code)
        mood, _ = create_mood(self.alice, "missing")
        self.assertEqual(mood.connection_id, connection.id)
        notification = Notification.objects.get(mood=mood)
        self.assertEqual(notification.recipient, self.bob)
        reaction, _ = create_reaction(self.bob, "hug", mood.id)
        self.assertEqual(reaction.recipient, self.alice)
        reaction_note = Notification.objects.get(reaction=reaction)
        self.assertEqual(reaction_note.recipient, self.alice)
        outsider = User.objects.create_user(username="outsider", password="o-strong-password-123")
        self.client.force_login(outsider)
        response = self.client.get(reverse("moments"))
        self.assertRedirects(response, reverse("connect"))
        self.assertFalse(Mood.objects.filter(connection=connection, sender=outsider).exists())

    def test_mood_endpoint_rejects_invalid_mood_and_accepts_valid_mood(self):
        invite = invite_for(self.alice)
        connect_with_code(self.bob, invite.code)
        self.client.force_login(self.alice)
        invalid = self.client.post(reverse("api_mood"), data="{\"mood_type\":\"secret\"}", content_type="application/json")
        self.assertEqual(invalid.status_code, 400)
        valid = self.client.post(reverse("api_mood"), data="{\"mood_type\":\"love\"}", content_type="application/json")
        self.assertEqual(valid.status_code, 200)
        self.assertEqual(Mood.objects.filter(sender=self.alice).count(), 1)

    def test_push_subscription_can_be_registered_and_removed_for_authenticated_user(self):
        self.client.force_login(self.alice)
        payload = '{"subscription":{"endpoint":"https://push.example.test/sub/abc","keys":{"p256dh":"public-key","auth":"auth-key"}}}'
        subscribed = self.client.post(reverse("push_subscribe"), data=payload, content_type="application/json")
        self.assertEqual(subscribed.status_code, 200)
        self.assertTrue(PushSubscription.objects.filter(user=self.alice).exists())
        removed = self.client.post(reverse("push_unsubscribe"), data='{"endpoint":"https://push.example.test/sub/abc"}', content_type="application/json")
        self.assertEqual(removed.status_code, 200)
        self.assertFalse(PushSubscription.objects.filter(user=self.alice).exists())

    def test_service_worker_is_available_at_root_scope(self):
        response = self.client.get(reverse("service_worker"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("showNotification", response.content.decode())

    def test_dashboard_and_settings_render_notification_controls(self):
        invite = invite_for(self.alice)
        connect_with_code(self.bob, invite.code)
        self.client.force_login(self.alice)
        dashboard = self.client.get(reverse("dashboard"))
        settings = self.client.get(reverse("settings"))
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(settings.status_code, 200)
        self.assertContains(settings, "Browser notifications")
        self.assertContains(settings, "Feeling sounds")

    def test_dashboard_state_reports_the_current_partner_mood(self):
        invite = invite_for(self.alice)
        connection, _ = connect_with_code(self.bob, invite.code)
        create_mood(self.bob, "missing")
        self.client.force_login(self.alice)

        response = self.client.get(reverse("dashboard_state"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["partner_mood"]["type"], "missing")
        self.assertEqual(response.json()["partner_mood"]["id"], Mood.objects.get(connection=connection, sender=self.bob).id)


class WebsocketAuthorizationTests(TestCase):
    def test_anonymous_websocket_is_rejected(self):
        communicator = WebsocketCommunicator(application, "/ws/couple/")
        connected, _ = async_to_sync(communicator.connect)()
        self.assertFalse(connected)

