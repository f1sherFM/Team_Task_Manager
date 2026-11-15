from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile

User = get_user_model()


class ProfileSignalAndModelTests(TestCase):
    def test_profile_auto_created_on_user_creation(self):
        user = User.objects.create_user(username="testuser", password="secretpassword123")
        self.assertTrue(hasattr(user, "profile"))
        self.assertIsInstance(user.profile, Profile)
        self.assertEqual(str(user.profile), "Profile<testuser>")

    def test_profile_bio_and_avatar_update(self):
        user = User.objects.create_user(username="bio_user", password="secretpassword123")
        profile = user.profile
        profile.bio = "Backend developer working on TTM."
        profile.save()

        profile.refresh_from_db()
        self.assertEqual(profile.bio, "Backend developer working on TTM.")

    def test_existing_user_save_does_not_create_duplicate_profile(self):
        user = User.objects.create_user(username="stable_user", password="secretpassword123")
        profile_id = user.profile.id
        user.first_name = "NewName"
        user.save()

        self.assertEqual(Profile.objects.filter(user=user).count(), 1)
        self.assertEqual(user.profile.id, profile_id)


class SignUpViewTests(TestCase):
    def test_signup_page_renders_form(self):
        response = self.client.get(reverse("signup"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/signup.html")
        self.assertContains(response, "Sign up")

    def test_signup_creates_user_and_logs_in(self):
        response = self.client.post(
            reverse("signup"),
            {
                "username": "newuser",
                "email": "newuser@example.com",
                "password1": "Password123!",
                "password2": "Password123!",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("home"))

        user = User.objects.get(username="newuser")
        self.assertEqual(user.email, "newuser@example.com")
        self.assertTrue(hasattr(user, "profile"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_signup_duplicate_username_fails(self):
        User.objects.create_user(username="existinguser", password="Password123!")
        response = self.client.post(
            reverse("signup"),
            {
                "username": "existinguser",
                "email": "diff@example.com",
                "password1": "Password123!",
                "password2": "Password123!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context["form"],
            "username",
            "A user with that username already exists.",
        )


class LoginLogoutViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="loginuser", password="SafePassword123!")

    def test_login_page_renders(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/login.html")

    def test_login_successful_redirects_home(self):
        response = self.client.post(
            reverse("login"),
            {
                "username": "loginuser",
                "password": "SafePassword123!",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("home"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_login_invalid_password_shows_error(self):
        response = self.client.post(
            reverse("login"),
            {
                "username": "loginuser",
                "password": "WrongPassword!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please enter a correct username and password")

    def test_logout_redirects_to_login(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("logout"))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("login"))
        self.assertNotIn("_auth_user_id", self.client.session)
