from __future__ import annotations
from django import forms
from django.contrib.auth import get_user_model
from .models import Profile

User = get_user_model()

class RegistrationForm(forms.ModelForm):
    password1 = forms.CharField(widget=forms.PasswordInput, strip=False)
    password2 = forms.CharField(widget=forms.PasswordInput, strip=False)

    class Meta:
        model = User
        fields = ["username"]

    def clean_username(self):
        u = self.cleaned_data.get("username", "").strip()
        if not u:
            raise forms.ValidationError("Username required")
        # keep basic allowed chars policy (alphanumeric + underscore + dash)
        # rely on Django's default validators as well
        return u

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Passwords do not match")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class ProfileForm(forms.ModelForm):
    # Write‑only secrets: show empty inputs; if left blank keep existing
    # Pre-populate and display existing secrets; users can clear by submitting blank.
    mastodon_token = forms.CharField(required=False, widget=forms.PasswordInput(render_value=True))
    bluesky_app_password = forms.CharField(required=False, widget=forms.PasswordInput(render_value=True))
    status_cafe_password = forms.CharField(required=False, widget=forms.PasswordInput(render_value=True))

    class Meta:
        model = Profile
        fields = [
            "website",
            "show_archive",
            "bio",
            "mastodon_instance",
            "mastodon_char_limit",
            "mastodon_token",
            "bluesky_handle",
            "bluesky_app_password",
            "status_cafe_username",
            "status_cafe_password",
            "crosspost_mastodon",
            "crosspost_bluesky",
            "crosspost_status_cafe",
        ]

    def save(self, commit=True):
        profile: Profile = super().save(commit=False)
        # Overwrite secrets even if blank (blank clears stored value)
        if "mastodon_token" in self.cleaned_data:
            profile.mastodon_token = self.cleaned_data.get("mastodon_token") or ""
        if "bluesky_app_password" in self.cleaned_data:
            profile.bluesky_app_password = self.cleaned_data.get("bluesky_app_password") or ""
        if "status_cafe_password" in self.cleaned_data:
            profile.status_cafe_password = self.cleaned_data.get("status_cafe_password") or ""
        if commit:
            profile.save()
        return profile
