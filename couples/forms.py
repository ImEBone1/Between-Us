from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Profile


class RegisterForm(UserCreationForm):
    first_name = forms.CharField(max_length=40, required=False, label="First name")
    email = forms.EmailField(required=False)

    class Meta:
        model = User
        fields = ("username", "first_name", "email", "password1", "password2")

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if not username:
            raise forms.ValidationError("Choose a username to continue.")
        return username


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ("display_name", "avatar_color", "mood_expiration_hours", "notifications_enabled", "do_not_disturb", "browser_notifications_enabled", "vibration_enabled", "sound_enabled")
        widgets = {
            "display_name": forms.TextInput(attrs={"placeholder": "What should your person call you?", "maxlength": 80}),
            "avatar_color": forms.HiddenInput(),
            "mood_expiration_hours": forms.Select(choices=[(6, "6 hours"), (12, "12 hours"), (24, "24 hours"), (48, "48 hours")]),
            "notifications_enabled": forms.CheckboxInput(),
            "do_not_disturb": forms.CheckboxInput(),
            "browser_notifications_enabled": forms.CheckboxInput(),
            "vibration_enabled": forms.CheckboxInput(),
            "sound_enabled": forms.CheckboxInput(),
        }

    def clean_mood_expiration_hours(self):
        hours = self.cleaned_data["mood_expiration_hours"]
        if hours not in {6, 12, 24, 48}:
            raise forms.ValidationError("Choose a valid mood duration.")
        return hours

