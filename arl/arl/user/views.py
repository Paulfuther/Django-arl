import traceback

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import Group
from django.contrib.auth.views import FormView, LoginView
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from twilio.base.exceptions import TwilioException

from arl.msg.helpers import (check_verification_token,
                             request_verification_token)
from arl.msg.tasks import send_sms_task
from arl.dsign.tasks import create_docusign_envelope_task
from .tasks import (send_newhire_template_email_task,
                    create_newhire_data_email,
                    save_user_to_db)
from .forms import CustomUserCreationForm, TwoFactorAuthenticationForm
from .models import CustomUser, Employer, Store


class RegisterView(FormView):
    template_name = "user/index.html"
    form_class = CustomUserCreationForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["Employer"] = Employer.objects.all()
        context["Store"] = Store.objects.all()
        return context

    def form_valid(self, form):
        try:
            verified_phone_number = self.request.POST.get("phone_number")
            if verified_phone_number is None:
                raise Http404("Phone number not found in form data.")

            user = form.save(commit=False)
            user.phone_number = verified_phone_number
            # Serialize the form data
            serialized_data = self.serialize_user_data(form.cleaned_data)
            # Pass the serialized data as kwargs to the Celery task
            user = form.save(commit=False)
            user.save()
            serialized_data["user_id"] = user.id
            # Pass the serialized data as kwargs to the Celery task
            save_user_to_db.delay(**serialized_data)
            messages.success(
                self.request,
                "Thank you for registering. Please check your email for your New Hire File from Docusign.",
            )
            return redirect("home")

        except Exception as e:
            # Handle exceptions during form processing
            print(f"An error occurred during registration: {e}")
            traceback.print_exc()
            messages.error(self.request, "An error occurred during registration.")
            return redirect("home")

    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form))

    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def serialize_user_data(self, form_data):
        # Convert ForeignKey fields to their primary key values
        form_data["employer"] = (
            form_data["employer"].pk
            if "employer" in form_data and form_data["employer"] is not None
            else None
        )
        # Serialize store (assuming it's a ForeignKey field)
        form_data["store"] = (
            form_data["store"].pk
            if "store" in form_data and form_data["store"] is not None
            else None
        )

        # Serialize dob (assuming it's a DateField)
        form_data["dob"] = (
            form_data["dob"].isoformat()
            if "dob" in form_data and form_data["dob"] is not None
            else None
        )
        # form_data["country"] = (
        #    form_data["country"].isoformat()
        #    if "country" in form_data and form_data["country"] is not None
        #    else None)

        return form_data


# signal to trigger events post save of new use.
@receiver(post_save, sender=CustomUser)
def handle_new_hire_registration(sender, instance, created, **kwargs):
    if created:
        try:
            send_newhire_template_email_task.delay(
                instance.email,
                "Welcome Aboard",
                instance.first_name,
                settings.SENDGRID_NEWHIRE_ID,
            )
            # Assign user to group GSA
            gsa_group_name = "GSA"
            gsa_group, created = Group.objects.get_or_create(name=gsa_group_name)
            instance.groups.add(gsa_group)

            # Create Docusign new hire file
            envelope_args = {
                "signer_email": instance.email,
                "signer_name": instance.username,
                "template_id": settings.DOCUSIGN_TEMPLATE_ID,
            }
            create_docusign_envelope_task.delay(envelope_args)

            # Create HR new hire email
            country_code = instance.country.code if instance.country else None
            # Convert dob to a string in ISO 8601 format
            dob_serializable = (
                instance.dob.strftime("%Y-%m-%d") if instance.dob else None
            )

            email_data = {
                "firstname": instance.first_name,
                "lastname": instance.last_name,
                "store_number": instance.store.number if instance.store else None,
                "store_address": instance.store.address if instance.store else None,
                "email": instance.email,
                "mobilephone": instance.phone_number,
                "addressone": instance.address,
                "addresstwo": instance.address_two,
                "city": instance.city,
                "province": instance.state_province,
                "postal": instance.postal,
                "country": country_code,
                "sin_number": instance.sin,
                "dob": dob_serializable,
            }
            print(email_data)
            create_newhire_data_email.delay(**email_data)

            # Send SMS to the newly registered user
            send_sms_task.delay(
                instance.phone_number,
                "Welcome Aboard! Thank you for registering. Check your email for a link to Docusign to complete your new hire file",
            )

        except Exception as e:
            # Handle exceptions or errors
            print(f"Error during new hire registration: {e}")


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
            return JsonResponse(
                {"success": False, "error": "Failed to send verification code"}
            )
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
            return JsonResponse(
                {"success": False, "error": "Failed to send verification code"}
            )
    return JsonResponse({"success": False, "error": "Invalid request method"})


def login_view(request):
    if request.user.is_authenticated:
        # If the user is already logged in,
        # redirect them to the homepage or any other URL.
        return redirect("home")
    if request.method == "POST":
        form = AuthenticationForm(request, request.POST)
        if form.is_valid():
            user = form.get_user()
            # Commented out the two-factor authentication section for now
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
                        request,
                        "user/login.html",
                        {"form": form, "verification_error": True},
                    )
            return redirect("home")

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
    return redirect(
        "home"
    )  # Replace 'home' with your desired URL name for the homepage\


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
                    self.request.session[
                        "user_id"
                    ] = user.id  # Store user ID in the session
                    self.request.session["phone_number"] = user.phone_number
                    return redirect("admin_verification_page")

                except TwilioException as e:
                    messages.error(
                        self.request, f"Failed to send verification code: {e}"
                    )
                    # Redirect back to the login page (you may need to specify the correct URL name)
                    return redirect(reverse("custom_admin_login"))
            return redirect("admin:index")


def fetch_managers(request):
    employer_id = request.GET.get("employer", None)

    if employer_id:
        try:
            # Get the employer based on the provided ID
            employer = get_object_or_404(Employer, id=employer_id)

            # Get all active users with the group "Manager" for the selected employer
            managers = CustomUser.objects.filter(
                groups__name="Manager", is_active=True, employer=employer
            )

            # Serialize the manager data with both username and ID
            manager_data = [
                {"id": manager.id, "username": manager.username} for manager in managers
            ]
            return JsonResponse(manager_data, safe=False)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    else:
        return JsonResponse({"error": "No employer ID provided"}, status=400)
