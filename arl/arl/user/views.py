import base64
import io
import logging
import os
import traceback
from functools import wraps
from django.utils import timezone
import qrcode
from celery import chain
from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import Group
from django.contrib.auth.views import LoginView
from django.core.paginator import Paginator
from django.db.models import Q
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import FormView, ListView
from django_celery_results.models import TaskResult
from django_otp import user_has_device
from django_otp.plugins.otp_totp.models import TOTPDevice
from phonenumbers import PhoneNumberFormat, format_number, is_valid_number, parse
from phonenumbers.phonenumberutil import NumberParseException
from twilio.base.exceptions import TwilioException
from twilio.rest import Client

from arl.bucket.helpers import download_from_s3
from arl.dsign.models import DocuSignTemplate, SignedDocumentFile
from arl.dsign.tasks import create_docusign_envelope_task
from arl.msg.helpers import check_verification_token, request_verification_token
from arl.msg.models import EmailTemplate
from arl.msg.tasks import send_sms_task
from arl.setup.helpers import employer_hr_required
from arl.setup.models import EmployerRequest

from .forms import (
    CustomUserCreationForm,
    NewHireInviteForm,
    TwoFactorAuthenticationForm,
)
from .models import CustomUser, Employer, EmployerSettings, NewHireInvite
from .tasks import (
    create_newhire_data_email,
    notify_hr_about_departure,
    save_user_to_db,
    send_new_hire_invite_task,
    send_newhire_template_email_task,
)
from .helpers import send_new_hire_invite

User = get_user_model()
logger = logging.getLogger(__name__)


class RegisterView(FormView):
    template_name = "user/register.html"
    form_class = CustomUserCreationForm

    def get(self, request, *args, **kwargs):
        """
        Displays the registration form only if the token is valid.
        """
        token = kwargs.get("token")
        print(f"🔹 Received Token: {token}")
        invite = get_object_or_404(
            NewHireInvite, token=token, used=False
        )  # ✅ Ensure the token is valid

        form = CustomUserCreationForm(
            initial={
                "email": invite.email,
                "employer": invite.employer,
                "phone_number": "",
            }
        )
        return self.render_form(request, form, invite)

    def form_valid(self, form):
        try:
            print(form.data)
            token = self.kwargs.get("token")
            invite = get_object_or_404(NewHireInvite, token=token, used=False)
            verified_phone_number = self.request.POST.get("phone_number")
            if verified_phone_number is None:
                raise Http404("Phone number not found in form data.")

            user = form.save(commit=False)
            user.phone_number = verified_phone_number
            user.employer = invite.employer
            # Serialize the form data
            serialized_data = self.serialize_user_data(form.cleaned_data)
            print(serialized_data)
            # Pass the serialized data as kwargs to the Celery task
            user = form.save(commit=False)
            user.save()
            serialized_data["user_id"] = user.id
            # Pass the serialized data as kwargs to the Celery task
            save_user_to_db.delay(**serialized_data)
            messages.success(
                self.request,
                "Thank you for registering. Check your email for a new hire file from Docusign.",
            )
            return redirect("home")

        except Exception as e:
            # Handle exceptions during form processing
            print(f"An error occurred during registration: {e}")
            traceback.print_exc()
            messages.error(self.request, "An error occurred during registration.")
            return redirect("home")

    def form_invalid(self, form):
        """
        If the form is invalid, retain pre-filled values.
        """
        print(form.data)
        token = self.kwargs.get("token")
        invite = get_object_or_404(NewHireInvite, token=token, used=False)

        # ✅ Ensure employer and phone_number persist
        form.data = form.data.copy()  # Make form data mutable
        form.data["employer"] = invite.employer.id  # Set employer ID
        form.data["phone_number"] = self.request.POST.get("phone_number", "")
        form.fields["employer"].queryset = Employer.objects.filter(
            id=invite.employer.id
        )

        return self.render_form(self.request, form, invite)

    def render_form(self, request, form, invite):
        """✅ Fix: Helper function to render the form properly"""
        return render(request, "user/register.html", {"form": form, "invite": invite})

    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def serialize_user_data(self, form_data):
        # Convert ForeignKey fields to their primary key values
        # and serialise certain data to pass to celery.
        form_data["employer"] = (
            form_data["employer"].pk
            if "employer" in form_data and form_data["employer"] is not None
            else None
        )
        form_data["store"] = (
            form_data["store"].pk
            if "store" in form_data and form_data["store"] is not None
            else None
        )
        form_data["dob"] = (
            form_data["dob"].isoformat()
            if "dob" in form_data and form_data["dob"] is not None
            else None
        )
        form_data["sin_expiration_date"] = (
            form_data["sin_expiration_date"].isoformat()
            if form_data.get("sin_expiration_date") is not None
            else None
        )
        form_data["work_permit_expiration_date"] = (
            form_data["work_permit_expiration_date"].isoformat()
            if form_data.get("work_permit_expiration_date") is not None
            else None
        )
        if "phone_number" in form_data and form_data["phone_number"]:
            form_data["phone_number"] = str(form_data["phone_number"])
        return form_data


# signal to trigger events post save of new use.
# Approved for Multi Tenant
@receiver(post_save, sender=CustomUser)
def handle_new_hire_registration(sender, instance, created, **kwargs):
    """Handles new hire registration by triggering necessary tasks."""
    if not created:
        return  # Exit early if the user was just updated

    try:
        # ✅ Find the invite that was used for registration
        invite = NewHireInvite.objects.filter(email=instance.email, used=False).first()

        if invite:
            role = invite.role  # ✅ Assign the role from the invite
            invite.used = True  # ✅ Mark the invite as used
            invite.save()
        else:
            print(f"❌ No invite found for {instance.email}. Defaulting to GSA.")
            role = "GSA"  # Default role if no invite is found

        # ✅ Assign the user to the correct group based on the role
        role_group, _ = Group.objects.get_or_create(name=role)
        instance.groups.add(role_group)
        print(f"✅ User {instance.email} assigned to group: {role}")

        employer = instance.employer

        if not employer:
            print(
                f"❌ No employer found for user {instance.email}. Skipping new hire setup."
            )
            return

        # ✅ Fetch Employer Settings (once)
        employer_settings = EmployerSettings.objects.filter(employer=employer).first()

        # ✅ Default behavior
        send_new_hire_file = False

        if employer_settings:
            send_new_hire_file = employer_settings.send_new_hire_file
            print(f"📌 Employer Settings Found for {employer.name}")
            print(f"📌 send_new_hire_file: {send_new_hire_file}")
        else:
            print(
                f"🚨 No EmployerSettings found for {employer.name}. Defaulting to False."
            )

        # ✅ Retrieve the DocuSign Template
        docusign_template = None
        template_id = None

        if send_new_hire_file:
            docusign_template = DocuSignTemplate.objects.filter(
                employer=employer, is_new_hire_template=True
            ).first()

            if docusign_template:
                template_id = docusign_template.template_id
                print(f"📄 New Hire Template Found: {docusign_template.template_name}")
            else:
                print("⚠️ No DocuSign template marked as 'new hire' found.")

        print("Docusign Template id:", template_id)

        # ✅ Get Email Template
        email_template = EmailTemplate.objects.filter(
            employers=employer, name="New_Hire_Onboarding"
        ).first()

        sendgrid_id = None
        if email_template:
            sendgrid_id = email_template.sendgrid_id
        else:
            print(
                f"⚠️ No 'New Hire Onboarding' email template assigned to {employer.name}. Skipping email."
            )

        # ✅ Default fallback name for sender
        senior_contact_name = getattr(employer, "senior_contact_name", "HR Team")

        # ✅ Debugging prints
        print(f"👔 Employer: {employer.name}")
        print(f"📩 SendGrid Template: {sendgrid_id}")
        print(f"👤 Senior Contact Name: {senior_contact_name}")
        print(f"📜 DocuSign Enabled? {send_new_hire_file}")
        print(
            f"📑 DocuSign Template: {docusign_template.template_name if docusign_template else 'None'}"
        )
        print(f"📜 DocuSign Template ID: {template_id}")

        # ✅ Format phone number (if exists)
        formatted_phone = (
            format_number(instance.phone_number, PhoneNumberFormat.E164)
            if instance.phone_number
            else None
        )

        # ✅ Serialize dates safely (handles None values)
        def serialize_date(date_obj):
            return date_obj.strftime("%Y-%m-%d") if date_obj else None

        # ✅ Prepare email template data
        template_data = {
            "name": instance.first_name,
            "senior_contact_name": senior_contact_name,
            "company_name": employer.name,
        }

        # ✅ Prepare email data for HR
        email_data = {
            "firstname": instance.first_name,
            "lastname": instance.last_name,
            "store_number": instance.store.number if instance.store else None,
            "store_address": instance.store.address if instance.store else None,
            "email": instance.email,
            "mobilephone": formatted_phone,
            "addressone": instance.address,
            "addresstwo": instance.address_two,
            "city": instance.city,
            "province": instance.state_province,
            "postal": instance.postal,
            "country": instance.country.code if instance.country else None,
            "sin_number": instance.sin,
            "dob": serialize_date(instance.dob),
            "sin_expiration_date": serialize_date(instance.sin_expiration_date),
            "work_permit_expiration_date": serialize_date(
                instance.work_permit_expiration_date,
            ),
            "employer_id": instance.employer_id,
        }

        # ✅ First part: Always send new hire template email and HR data
        initial_tasks = chain(
            send_newhire_template_email_task.s(
                instance.email, sendgrid_id, template_data
            ),
            create_newhire_data_email.s(email_data).set(immutable=True),
        )

        # ✅ If DocuSign is enabled, add DocuSign + SMS to chain
        if send_new_hire_file and template_id:
            docusign_tasks = chain(
                create_docusign_envelope_task.s(
                    {
                        "signer_email": instance.email,
                        "signer_name": instance.username,
                        "template_id": template_id,  # ✅ Use employer-specific template
                    }
                ).set(immutable=True),
                send_sms_task.s(
                    formatted_phone,
                    "Welcome Aboard! Thank you for registering. Check your email for a link to DocuSign to complete your new hire file.",
                ).set(immutable=True),
            )
            final_task_chain = chain(initial_tasks, docusign_tasks)  # Merge chains
        else:
            final_task_chain = initial_tasks  # No DocuSign tasks

        # ✅ Dispatch the task chain
        final_task_chain.apply_async()

    except Exception as e:
        print(f"❌ Error during new hire registration: {e}")


class CheckPhoneNumberUniqueView(View):
    def post(self, request):
        phone_number = request.POST.get("phone_number")
        print("unique number?", phone_number)
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


# Works.
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
        return redirect("home")

    if request.method == "POST":
        form = AuthenticationForm(request, request.POST)
        if form.is_valid():
            user = form.get_user()
            if user.phone_number:
                print(f"DEBUG: Phone number before sending: {str(user.phone_number)}")
                try:
                    phone_number = str(user.phone_number)  # Ensure string conversion
                    request.session["user_id"] = user.id
                    request_verification_token(phone_number)  # ✅ Pass string to Twilio
                    request.session["phone_number"] = (
                        phone_number  # ✅ Ensure session stores string
                    )
                    return redirect("verification_page")
                except TwilioException:
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
        user = form.get_user()

        if user and user.is_active:
            # ✅ Check for confirmed MFA device
            if user_has_device(user, confirmed=True):
                # ✅ Check if this session is verified
                if not hasattr(self.request, "otp_device"):
                    # User is not yet MFA-verified in this session
                    self.request.session["pre_2fa_user_id"] = user.id
                    return redirect("admin_verify_totp")
            else:
                # User is not enrolled — redirect to setup
                self.request.session["pre_2fa_user_id"] = user.id
                return redirect("admin_setup_mfa")

            # ✅ Passed all checks — log in
            login(self.request, user)
            return redirect("admin:index")

        messages.error(self.request, "Login failed.")
        return redirect("custom_admin_login")


def verify_totp(request):
    user_id = request.session.get("pre_2fa_user_id")
    if not user_id:
        messages.error(request, "Session expired. Please log in again.")
        return redirect("custom_admin_login")

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        messages.error(request, "Invalid user.")
        return redirect("custom_admin_login")

    device = TOTPDevice.objects.filter(user=user, confirmed=True).first()
    if not device:
        messages.error(request, "No verified MFA device found.")
        return redirect("admin_setup_mfa")

    if request.method == "POST":
        token = request.POST.get("token")
        if device.verify_token(token):
            login(request, user)
            request.session.pop("pre_2fa_user_id", None)
            request.otp_device = device
            messages.success(request, "MFA verified successfully.")
            return redirect("admin:index")
        else:
            messages.error(request, "Invalid verification code.")

    # ✅ Always return a response on GET or after invalid POST
    return render(request, "admin/verify_totp.html")


def require_pre_2fa(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if "pre_2fa_user_id" not in request.session:
            return redirect("custom_admin_login")
        return view_func(request, *args, **kwargs)

    return _wrapped_view


@require_pre_2fa
def setup_totp(request):
    user_id = request.session.get("pre_2fa_user_id")
    if not user_id:
        return redirect("custom_admin_login")

    user = User.objects.get(id=user_id)

    if TOTPDevice.objects.filter(user=user, confirmed=True).exists():
        messages.info(request, "You already have MFA set up.")
        return redirect("admin:index")

    # Check for unconfirmed device
    device = TOTPDevice.objects.filter(user=user, confirmed=False).first()
    if not device:
        device = TOTPDevice.objects.create(
            user=user, name="Admin TOTP", confirmed=False
        )

    qr = qrcode.make(device.config_url)
    buffer = io.BytesIO()
    qr.save(buffer, format="PNG")
    qr_data_uri = base64.b64encode(buffer.getvalue()).decode("utf-8")

    if request.method == "POST":
        token = request.POST.get("token")
        if device.verify_token(token):
            device.confirmed = True
            device.save()

            # ✅ Now log the user in
            from django.contrib.auth import login

            login(request, user)

            request.session.pop("pre_2fa_user_id", None)
            messages.success(request, "MFA setup complete.")
            return redirect("admin:index")
        else:
            messages.error(request, "Invalid token. Please try again.")

    return render(
        request,
        "admin/setup_totp.html",
        {
            "qr_code": f"data:image/png;base64,{qr_data_uri}",
        },
    )


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


class TaskResultListView(ListView):
    model = TaskResult
    template_name = "user/task_results.html"
    context_object_name = "task_results"
    paginate_by = 10  # Optional: Paginate results if there are many


def verify_twilio_phone_number(request, phone_number):
    # Get the phone number from query parameters
    phone_number = "+13828852897"

    if not phone_number:
        return JsonResponse({"error": "Phone number parameter is required"}, status=400)

    try:
        # Perform lookup with all available data packages
        # Using Lookup v2 API for more comprehensive response
        lookup = client.lookups.v2.phone_numbers(phone_number).fetch(
            fields="line_type_intelligence,caller_name,sim_swap,identity_match"
        )

        # Construct the response dictionary with all available data
        response_data = {
            "phone_number": lookup.phone_number,
            "national_format": lookup.national_format,
            "country_code": lookup.country_code,
            "valid": lookup.valid,
            "validation_errors": lookup.validation_errors,
            "caller_name": lookup.caller_name,
            "line_type_intelligence": lookup.line_type_intelligence,
            "sim_swap": lookup.sim_swap,
            "identity_match": lookup.identity_match,
            "url": lookup.url,
        }

        return JsonResponse({"status": "success", "data": response_data})

    except TwilioRestException as e:
        return JsonResponse(
            {
                "status": "error",
                "message": str(e),
                "code": e.code if hasattr(e, "code") else None,
            },
            status=400,
        )

    except Exception as e:
        return JsonResponse(
            {"status": "error", "message": f"An unexpected error occurred: {str(e)}"},
            status=500,
        )


# Works to verify if a phone number is an actual phone number
# And formats it properly for the db.
def phone_format(request):
    """Formats a phone number to E.164 format and returns it via JSON response."""
    if request.method == "GET":  # Use GET instead of POST
        raw_input = request.GET.get("phone_number", "").strip()
        print("raw input :", raw_input)
        try:
            parsed_number = parse(
                raw_input, "CA"
            )  # "CA" is for Canada, change as needed
            # ✅ Check if the number is valid
            if not is_valid_number(parsed_number):
                return JsonResponse(
                    {"error": "Invalid or non-existent phone number."}, status=400
                )
            formatted_e164 = format_number(
                parsed_number, PhoneNumberFormat.E164
            )  # Standardized format
            formatted_national = format_number(
                parsed_number, PhoneNumberFormat.NATIONAL
            )  # Local format

            return JsonResponse(
                {
                    "formatted_phone_number": formatted_e164,  # Store this in the hidden input
                    "national_format": formatted_national,
                    "message": "Phone number is valid and formatted.",
                },
                status=200,
            )

        except NumberParseException:
            return JsonResponse({"error": "Invalid phone number format."}, status=400)

    return JsonResponse({"error": "Invalid request method."}, status=405)


def landing_page(request):
    """Landing page where new employers can request access and existing users can log in."""
    return render(request, "user/landing_page.html")


@login_required
def hr_dashboard(request):
    """HR Dashboard: Invite new hires and manage DocuSign templates."""
    employer = request.user.employer  # Get employer data

    # ✅ Restrict access to Managers & Employers only
    if (
        not employer
        or not request.user.groups.filter(name__in=["Manager", "EMPLOYER"]).exists()
    ):
        messages.error(
            request, "You must be an employer or manager to invite new hires."
        )
        return redirect("home")

    templates = DocuSignTemplate.objects.filter(employer=employer).order_by(
        "-is_new_hire_template", "template_name"
    )
    for template in templates:
        template.template_status = (
            "Ready to Send" if template.is_ready_to_send else "Incomplete"
        )

    pending_invites = NewHireInvite.objects.filter(
        employer=employer, used=False
    )  # Fetch pending invites

    if request.method == "POST":
        form = NewHireInviteForm(request.POST, employer=employer)

        if form.is_valid():
            email = form.cleaned_data["email"]
            departed_name = form.cleaned_data.get("departed_name")
            departed_email = form.cleaned_data.get("departed_email")

            if CustomUser.objects.filter(email=email).exists():
                messages.error(request, f"A user with email {email} already exists.")
                return HttpResponseRedirect(reverse("hr_dashboard") + "?tab=employees")

            if departed_name or departed_email:
                notify_hr_about_departure.delay(
                    departed_name=departed_name,
                    departed_email=departed_email,
                    employer_id=request.user.employer_id,
                )

            invite = form.save()

            send_new_hire_invite_task.delay(
                new_hire_email=invite.email,
                new_hire_name=invite.name,
                role=invite.role,
                start_date="TBD",
                employer_id=employer.id,
            )

            messages.success(request, f"Invite sent to {invite.name}  {invite.email}")
            return HttpResponseRedirect(reverse("hr_dashboard") + "?tab=employees")

        else:
            # Save the form in the session to repopulate it after redirect (optional)
            request.session["form_errors"] = form.errors
            request.session["form_data"] = request.POST
            messages.error(request, "Please correct the errors in the form.")
            return HttpResponseRedirect(reverse("hr_dashboard") + "?tab=employees")

    # ✅ Handle GET request
    if "form_errors" in request.session:
        form = NewHireInviteForm(
            data=request.session.get("form_data"), employer=employer
        )
        form._errors = request.session.pop("form_errors")
        request.session.pop("form_data", None)
    else:
        form = NewHireInviteForm(employer=employer)

    # ✅ Check for DocuSign event
    event = request.GET.get('event')
    tab = request.GET.get('tab')
    document_tab = request.GET.get('document_tab', 'employee')
    if event and not tab:
        # ✅ If coming back from signing and no tab selected, default to "docusign"
        active_tab = "docusign"
    else:
        active_tab = tab or "docusign"  # Default to docusign if nothing else is provided

    if event == "signing_complete":
        messages.success(request, "✅ Thanks for signing your document!")
    elif event == "decline":
        messages.warning(request, "⚠️ You declined to sign the document.")
    elif event == "cancel":
        messages.warning(request, "⚠️ You canceled signing the document.")    

    # ✅ Fetch employee documents (is_company_document = False)
    employee_documents = SignedDocumentFile.objects.filter(
        employer=employer,
        is_company_document=False
    )

    # ✅ Fetch company documents (is_company_document = True)
    company_documents = SignedDocumentFile.objects.filter(
        employer=employer,
        is_company_document=True
    )

    return render(
        request,
        "user/hr_dashboard.html",
        {
            "form": form,
            "templates": templates,
            "pending_invites": pending_invites,
            "active_tab": active_tab,
            "document_tab": document_tab,
            "employer": employer,
            "employee_documents": employee_documents,
            "company_documents": company_documents,
        },
    )


@login_required
def cancel_invite(request, invite_id):
    """Allows HR to cancel a new hire invitation."""
    invite = get_object_or_404(
        NewHireInvite, id=invite_id, employer=request.user.employer
    )

    if invite.used:
        messages.error(
            request, "This invite has already been used and cannot be canceled."
        )
    else:
        invite.delete()
        messages.success(request, f"Invite for {invite.email} has been canceled.")

    return HttpResponseRedirect(reverse("hr_dashboard") + "?tab=employees")


@login_required
def resend_invite(request, invite_id):
    """Allows HR to resend a new hire invitation."""
    invite = get_object_or_404(
        NewHireInvite, id=invite_id, employer=request.user.employer
    )

    if invite.used:
        messages.error(
            request, "This invite has already been used and cannot be resent."
        )
    else:
        # ✅ Resend the invite email
        send_new_hire_invite(
            new_hire_email=invite.email,
            new_hire_name=invite.name,
            role=invite.role,
            start_date="TBD",
            employer=invite.employer,
        )
        messages.success(request, f"Invite for {invite.email} has been resent.")

    return HttpResponseRedirect(reverse("hr_dashboard") + "?tab=employees")


@login_required
def reject_employer(request, pk):
    employer_request = get_object_or_404(EmployerRequest, pk=pk)

    if employer_request.status != "pending":
        messages.warning(request, "This request has already been processed.")
        return redirect("/admin/user/employerrequest/")

    # ✅ Mark request as rejected
    employer_request.status = "rejected"
    employer_request.save()

    messages.error(
        request, f"Employer request for {employer_request.name} has been rejected."
    )
    return redirect("/admin/user/employerrequest/")


@login_required
def close_twilio_sub(request, subaccount_sid):
    """
    View to close a Twilio subaccount.
    """
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")

    if not account_sid or not auth_token:
        return HttpResponse("❌ Twilio credentials not found.", status=400)

    try:
        client = Client(account_sid, auth_token)
        account = client.api.v2010.accounts(subaccount_sid).update(status="closed")
        return HttpResponse(
            f"✅ Twilio subaccount {subaccount_sid} closed successfully.", status=200
        )

    except Exception as e:
        return HttpResponse(f"❌ Error closing Twilio subaccount: {str(e)}", status=500)


def hr_document_view(request):
    query = request.GET.get("q", "").strip()
    employer = request.user.employer

    employees = CustomUser.objects.filter(employer=employer, is_active=True)
    if query:
        employees = employees.filter(
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
        )

    employees = employees.prefetch_related("signed_documents")

    return render(
        request, "dsign/partials/employee_document_table.html", {"employees": employees}
    )


def download_signed_document(request, doc_id):
    try:
        print(doc_id)
        # 🔍 Get the uploaded document
        doc = get_object_or_404(SignedDocumentFile, id=doc_id)

        # 🧼 Build a clean, dynamic filename
        employee_name = doc.user.get_full_name().replace(" ", "_") if doc.user else "Company"
        template_clean = doc.template_name.replace(" ", "_") if doc.template_name else "Untitled"
        today = timezone.now().strftime("%Y-%m-%d")
        custom_filename = f"{employee_name}_{template_clean}_{today}.pdf"

        # 🔥 Pass this custom filename into download_from_s3
        return download_from_s3(request, doc.file_path, custom_filename)

    except Exception as e:
        print(f"Error in download_signed_document: {str(e)}")
        return HttpResponse("Error downloading signed document", status=500)


def fetch_signed_docs_by_user(request, user_id):
    user = get_object_or_404(CustomUser, id=user_id)
    documents = SignedDocumentFile.objects.filter(user=user).order_by("-uploaded_at")

    # 🔁 Get per_page from query param or default to 3
    try:
        per_page = int(request.GET.get("per_page", 6))
    except ValueError:
        per_page = 3

    # Paginate
    paginator = Paginator(documents, per_page)  # Show 5 per page
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "dsign/partials/document_results.html",
        {
            "employee_id": user.id,
            "page_obj": page_obj,
        },
    )


@login_required
@employer_hr_required
def search_user_roles(request):
    query = request.GET.get("query")
    employer = request.user.employer  # if you filter by employer
    users = CustomUser.objects.filter(employer=employer, is_active=True)

    if query:
        users = users.filter(
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
        )

    all_groups = Group.objects.all()  # Or filter to specific groups if needed
    return render(
        request,
        "user/hr/partials/user_role_results.html",
        {"users": users, "all_groups": all_groups},
    )


@login_required
@employer_hr_required
def update_user_roles(request, user_id):
    user = get_object_or_404(User, pk=user_id)

    if request.method == "POST":
        selected_group_ids = request.POST.getlist("groups")
        selected_groups = Group.objects.filter(id__in=selected_group_ids)

        user.groups.set(selected_groups)

        all_groups = Group.objects.all()
        users = User.objects.filter(employer=request.user.employer)

        return render(
            request,
            "user/hr/partials/user_role_list.html",
            {
                "users": users,
                "all_groups": all_groups,
            },
        )

    return HttpResponseBadRequest("Invalid request")
