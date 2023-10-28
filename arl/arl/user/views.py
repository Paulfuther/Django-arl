from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin import AdminSite
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import Group
from django.contrib.auth.views import LoginView, PasswordResetView
from django.contrib.messages.views import SuccessMessageMixin
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django_ratelimit.decorators import ratelimit
# from arl.msg.tasks import send_sms_task
from twilio.base.exceptions import TwilioException

from arl.msg.helpers import check_verification_token, request_verification_token
from arl.tasks import send_sms_task, send_template_email_task

from .forms import CustomUserCreationForm, TwoFactorAuthenticationForm
from .models import CustomUser, Employer


def register(request):
    employers = Employer.objects.all()  # Retrieve all employers from the database
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        print(form.data)
        if form.is_valid():
            verified_phone_number = request.POST.get("phone_number")
            print(verified_phone_number)
            user = form.save(commit=False)
            user.phone_number = verified_phone_number
            user.save()
            send_template_email_task.delay(
                user.email, "Welcome Aboard", user.first_name, settings.SENDGRID_NEWHIRE_ID
            )
            gsa_group = Group.objects.get(name="GSA")
            user.groups.add(gsa_group)
            return render(request, "msg/success.html")
    else:
        form = CustomUserCreationForm()
        print(form.errors)
    return render(request, "user/index.html", {"form": form, "Employer": employers})


class CheckPhoneNumberUniqueView(View):
    def post(self, request):
        phone_number = request.POST.get("phone_number")
        print(phone_number)
        if CustomUser.objects.filter(phone_number=phone_number).exists():
            return JsonResponse({"exists": True})
        else:
            return JsonResponse({"exists": False})


@login_required
def sms_form(request):
    if request.method == "POST":
        phone_number = request.POST.get("phone_number")
        if phone_number:
            print(phone_number)
            # Call the send_sms_task which calls function function with the phone_number
            send_sms_task.delay(phone_number)
            # Optionally, you can redirect to a success page or display a success message
            return render(request, "msg/success.html")
    else:
        # Display the form for GET requests
        return render(request, "msg/sms_form.html")


def request_verification(request):
    if request.method == "POST":
        phone_number = request.POST.get("phone_number")
        print("Phone number:", phone_number)  # Debugging statement
        try:
            # Request the verification code from Twilio
            request_verification_token(phone_number)
            # Verification request successful
            # Return a success response
            return JsonResponse({"success": True})
        except TwilioException:
            # Handle TwilioException if verification request fails
            return JsonResponse({"success": False, "error": "Failed to send verification code"})
    # Return an error response for unsupported request methods
    return JsonResponse({"success": False, "error": "Invalid request method"})


def check_verification(request):
    if request.method == "POST":
        phone = request.POST.get("phone_number")
        token = request.POST.get("verification_code")
        print("Phone number:", phone)
        print("Verification code:", token)
        print(phone, token)
        try:
            if check_verification_token(phone, token):
                return JsonResponse({"success": True})
        except TwilioException:
            return JsonResponse({"success": False, "error": "Failed to send verification code"})
    return JsonResponse({"success": False, "error": "Invalid request method"})


def login_view(request):
    if request.user.is_authenticated:
        # If the user is already logged in, redirect them to the homepage or any other URL.
        return redirect("home")
    if request.method == "POST":
        form = AuthenticationForm(request, request.POST)
        if form.is_valid():
            user = form.get_user()
            if user.phone_number:
                print(user.phone_number)
                try:
                    phone_number = user.phone_number
                    request.session["user_id"] = user.id
                    # Request the verification code from Twilio
                    request_verification_token(phone_number)
                    request.session["phone_number"] = phone_number
                    # Verification request successful
                    # Redirect to the verification page
                    return redirect("verification_page")
                except TwilioException:
                    # Handle TwilioException if verification request fails
                    return render(
                        request, "user/login.html", {"form": form, "verification_error": True}
                    )
            return redirect("home")  # Replace 'home' with your desired URL name for the homepage
    else:
        form = AuthenticationForm(request)
    return render(request, "user/login.html", {"form": form})


def verification_page(request):
    form = TwoFactorAuthenticationForm(request.POST)
    user_id = request.session.get("user_id", None)
    if not user_id:
        return HttpResponse(
            "User information not found in session. Please start the process again."
        )
    try:
        user = CustomUser.objects.get(id=user_id)
        print(user.username)
    except CustomUser.DoesNotExist:
        return HttpResponse("User not found.")

    if request.method == "POST":
        if form.is_valid():
            token = request.POST.get("verification_code")
            phone_number = request.session.get("phone_number", None)

            print("testing", token, phone_number)
            try:
                if check_verification_token(phone_number, token):
                    login(request, user)
                    return redirect("home")
                else:
                    return render(
                        request,
                        "user/verification_page.html",
                        {"verification_error": True, "form": form},
                    )
            except TwilioException:
                return render(
                    request,
                    "user/verification_page.html",
                    {"verification_error": True, "form": form},
                )

    return render(request, "user/verification_page.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("home")  # Replace 'home' with your desired URL name for the homepage\

#@ratelimit(key='user_or_ip', rate='5/m')
def home_view(request):
    return render(request, "user/home.html")


def admin_verification_page(request):
    form = TwoFactorAuthenticationForm(request.POST)
    user_id = request.session.get("user_id", None)
    if not user_id:
        return HttpResponse(
            "User information not found in session. Please start the process again."
        )
    try:
        user = CustomUser.objects.get(id=user_id)
        print(user.username)
    except CustomUser.DoesNotExist:
        return HttpResponse("User not found.")

    if request.method == "POST":
        token = request.POST.get("verification_code")
        phone_number = request.session.get("phone_number", None)

        print("testing", token, phone_number)
        try:
            if check_verification_token(phone_number, token):
                login(request, user)
                return redirect("admin:index")
            else:
                return render(
                    request,
                    "user/admin_verification_page.html",
                    {"verification_error": True, "form": form},
                )
        except TwilioException:
            return render(
                request,
                "user/admin_verification_page.html",
                {"verification_error": True, "form": form},
            )

    return render(request, "user/admin_verification_page.html", {"form": form})


class CustomAdminLoginView(LoginView):
    template_name = "registration/login.html"
    form_class = AuthenticationForm

    def form_invalid(self, form):
        # This method is called when the form is invalid (e.g., user doesn't exist).
        # You can display an error message here.
        messages.error(self.request, "Invalid username or password")
        return super().form_invalid(form)

    def form_valid(self, form):
        # Here, you can perform additional logic after a user successfully logs in.
        # For example, check if the user has 2FA enabled and redirect accordingly.
        user = form.get_user()
        print(user.username)
        # Implement your 2FA logic here
        if user and user.is_active:
            print("yah", user.phone_number)
            if user.phone_number:
                # Request the verification code from Twilio
                try:
                    request_verification_token(user.phone_number)
                    self.request.session["user_id"] = user.id  # Store user ID in the session
                    self.request.session["phone_number"] = user.phone_number
                    return redirect("admin_verification_page")

                except TwilioException as e:
                    messages.error(self.request, f"Failed to send verification code: {e}")
                    # Redirect back to the login page (you may need to specify the correct URL name)
                    return redirect(reverse("custom_admin_login"))
            return redirect("admin:index")



