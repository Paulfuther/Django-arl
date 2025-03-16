import traceback
from django.http import JsonResponse
from django.conf import settings
from phonenumbers import (parse, format_number, is_valid_number,
                          PhoneNumberFormat)
from phonenumbers.phonenumberutil import NumberParseException
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import Group
from django.contrib.auth.views import FormView, LoginView
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import ListView
from django_celery_results.models import TaskResult
from twilio.base.exceptions import TwilioException
from arl.msg.helpers import (check_verification_token,
                             request_verification_token)
from arl.msg.models import EmailTemplate
from arl.msg.tasks import send_sms_task
from celery import chain
from .forms import (CustomUserCreationForm, TwoFactorAuthenticationForm,
                    EmployerRegistrationForm, NewHireInviteForm,
                    NewHireInvite)
from .models import (CustomUser, Employer, EmployerSettings,
                     EmployerRequest)
from .tasks import (create_newhire_data_email, save_user_to_db,
                    send_newhire_template_email_task,
                    send_payment_email_task)
from arl.dsign.tasks import create_docusign_envelope_task
from arl.dsign.models import DocuSignTemplate
from .helpers import send_new_hire_invite
import stripe
import logging
import os
from twilio.rest import Client

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
        invite = get_object_or_404(NewHireInvite, token=token, used=False)  # ✅ Ensure the token is valid

        form = CustomUserCreationForm(
            initial={"email": invite.email, "employer": invite.employer, "phone_number": ""}
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
        form.data["employer"] = invite.employer.id # Set employer ID
        form.data["phone_number"] = self.request.POST.get("phone_number", "")
        form.fields["employer"].queryset = Employer.objects.filter(id=invite.employer.id)

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


class EmployerRegistrationView(FormView):
    template_name = "user/employer_registration.html"
    form_class = EmployerRegistrationForm
    success_url = reverse_lazy("employer_registration_success")

    def form_valid(self, form):
        employer_request = form.save(commit=False)
        employer_request.status = "pending"  # Mark as pending
        employer_request.save()

        messages.success(self.request, "Your request has been submitted for review. You will receive an email once approved.")
        return super().form_valid(form)


# signal to trigger events post save of new use.
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
        # ✅ Get Employer
        employer = instance.employer
        if not employer:
            print(f"❌ No employer found for user {instance.email}. Skipping new hire setup.")
            return

        # ✅ Retrieve `send_new_hire_file` setting from `EmployerSettings`
        send_new_hire_file = (
            EmployerSettings.objects.filter(employer=employer)
            .values_list("send_new_hire_file", flat=True)
            .first()
            or False
        )

        # ✅ Fetch Employer Settings
        employer_settings = EmployerSettings.objects.filter(employer=employer).first()

        # ✅ Ensure Employer Settings exist
        if not employer_settings:
            print(f"🚨 No EmployerSettings found for {employer.name}. Defaulting to False.")
            send_new_hire_file = False
        else:
            send_new_hire_file = employer_settings.send_new_hire_file
            print(f"📌 Employer Settings Found: {bool(employer_settings)}")
            print(f"📌 send_new_hire_file: {send_new_hire_file} (Expected: True)")


        # ✅ Retrieve the correct DocuSign template for this employer (if needed)
        docusign_template = None
        template_id = None
        if send_new_hire_file:
            docusign_template = DocuSignTemplate.objects.filter(
                employer=employer, template_name="New_Hire_File"
            ).first()

        template_id = docusign_template.template_id if docusign_template else None
        print("Docusign Template id :", template_id)
        email_template = EmailTemplate.objects.filter(
            employers=employer, name="New_Hire_Onboarding"
        ).first()

        if not email_template:
            print(f"⚠️ No 'New Hire Onboarding' email template assigned to {employer.name}. Skipping email.")
            sendgrid_id = None 

        sendgrid_id = email_template.sendgrid_id  
        senior_contact_name = getattr(employer, "senior_contact_name", "HR Team")
        # ✅ Debugging prints
        print(f"👔 Employer: {employer.name}")
        print(f"📩 SendGrid Template: {sendgrid_id}")
        print(f"👤 Senior Contact Name: {senior_contact_name}")
        print(f"📜 DocuSign Enabled? {send_new_hire_file}")
        print(f"📑 DocuSign Template: {docusign_template.template_name if docusign_template else 'None'}")
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
                instance.work_permit_expiration_date
            ),
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
                create_docusign_envelope_task.s({
                    "signer_email": instance.email,
                    "signer_name": instance.username,
                    "template_id": template_id,  # ✅ Use employer-specific template
                }).set(immutable=True),
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
                    request.session["phone_number"] = phone_number  # ✅ Ensure session stores string
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


class TaskResultListView(ListView):
    model = TaskResult
    template_name = 'user/task_results.html'
    context_object_name = 'task_results'
    paginate_by = 10  # Optional: Paginate results if there are many


def verify_twilio_phone_number(request, phone_number):
    # Get the phone number from query parameters
    phone_number = ("+13828852897")
    
    if not phone_number:
        return JsonResponse({
            'error': 'Phone number parameter is required'
        }, status=400)

    try:
        
        # Perform lookup with all available data packages
        # Using Lookup v2 API for more comprehensive response
        lookup = client.lookups.v2.phone_numbers(phone_number).fetch(
            fields='line_type_intelligence,caller_name,sim_swap,identity_match'
        )
        
        # Construct the response dictionary with all available data
        response_data = {
            'phone_number': lookup.phone_number,
            'national_format': lookup.national_format,
            'country_code': lookup.country_code,
            'valid': lookup.valid,
            'validation_errors': lookup.validation_errors,
            'caller_name': lookup.caller_name,
            'line_type_intelligence': lookup.line_type_intelligence,
            'sim_swap': lookup.sim_swap,
            'identity_match': lookup.identity_match,
            'url': lookup.url
        }
        
        return JsonResponse({
            'status': 'success',
            'data': response_data
        })

    except TwilioRestException as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e),
            'code': e.code if hasattr(e, 'code') else None
        }, status=400)

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'An unexpected error occurred: {str(e)}'
        }, status=500)


# Works to verify if a phone number is an actual phone number
# And formats it properly for the db.
def phone_format(request):
    """Formats a phone number to E.164 format and returns it via JSON response."""
    if request.method == 'GET':  # Use GET instead of POST
        raw_input = request.GET.get('phone_number', '').strip()
        print("raw input :",raw_input)
        try:
            parsed_number = parse(raw_input, "CA")  # "CA" is for Canada, change as needed
            # ✅ Check if the number is valid
            if not is_valid_number(parsed_number):
                return JsonResponse({"error": "Invalid or non-existent phone number."}, status=400)
            formatted_e164 = format_number(parsed_number, PhoneNumberFormat.E164)  # Standardized format
            formatted_national = format_number(parsed_number, PhoneNumberFormat.NATIONAL)  # Local format

            return JsonResponse({
                "formatted_phone_number": formatted_e164,  # Store this in the hidden input
                "national_format": formatted_national,
                "message": "Phone number is valid and formatted."
            }, status=200)

        except NumberParseException:
            return JsonResponse({"error": "Invalid phone number format."}, status=400)

    return JsonResponse({"error": "Invalid request method."}, status=405)


def landing_page(request):
    """Landing page where new employers can request access and existing users can log in."""
    return render(request, "user/landing_page.html")


@login_required
def hr_invite_new_hire(request):
    """Managers and Employers can invite a new hire"""
    employer = request.user.employer  # Get employer from logged-in user

    # ✅ Allow access if user is a Manager or Employer
    if not employer or not request.user.groups.filter(name__in=["Manager", "EMPLOYER"]).exists():
        messages.error(request, "You must be an employer or manager to invite new hires.")
        return redirect("home")  # Redirect to home if unauthorized

    if request.method == "POST":
        form = NewHireInviteForm(request.POST, employer=employer)

        if form.is_valid():
            email = form.cleaned_data["email"]
            print(email)
            # ✅ **Check if user already exists in the system**
            if CustomUser.objects.filter(email=email).exists():
                messages.error(request, f"A user with email {email} already exists.")
                return redirect("hr_invite")
            invite = form.save()
            send_new_hire_invite(
                new_hire_email=invite.email,
                new_hire_name=invite.name,
                role=invite.role,
                start_date="TBD",  # Can be added later
                employer=employer
            )
            messages.success(request, f"Invite sent to {invite.name} ({invite.email})")
            return redirect("hr_invite")  # Redirect back to form

    else:
        form = NewHireInviteForm(employer=employer)

    return render(request, "user/hr_invite.html", {"form": form})


@login_required
def approve_employer(request, pk):
    employer_request = get_object_or_404(EmployerRequest, pk=pk)

    if employer_request.status != "pending":
        messages.warning(request, "This request has already been processed.")
        return redirect("/admin/user/employerrequest/")

    # ✅ Generate verified sender local & email
    verified_sender_local_email = employer_request.verified_sender_local.lower().replace(" ", "").replace(".", "")
    verified_sender_email = f"{verified_sender_local_email}@1553690ontarioinc.com"

    # ✅ Create an Employer instance
    employer, created = Employer.objects.get_or_create(
        name=employer_request.name,
        defaults={
            "email": employer_request.email,
            "phone_number": employer_request.phone_number,  # Fixed field name
            "address": employer_request.address,
            "city": employer_request.city,
            "state_province": employer_request.state_province,
            "country": employer_request.country,
            "senior_contact_name": employer_request.senior_contact_name,
            "verified_sender_local": verified_sender_local_email,  # ✅ Add local sender
            "verified_sender_email": verified_sender_email,  # ✅ Add verified sender email
            "is_active": False,
        }
    )
    # ✅ If the employer already exists, update missing fields
    if not created:
        for field in [
            "email", "phone_number", "address", "city", "state_province",
            "country", "senior_contact_name", "verified_sender_local", "verified_sender_email"
        ]:
            if getattr(employer, field) is None and getattr(employer_request, field):
                setattr(employer, field, getattr(employer_request, field))
        employer.save()

    # ✅ Create Stripe checkout session
    stripe.api_key = settings.STRIPE_SECRET_KEY
    checkout_session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="subscription",
        customer_email=employer.email,
        line_items=[{"price": settings.STRIPE_PRICE_ID, "quantity": 1}],
        success_url=f"{settings.BASE_URL}/payment-success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{settings.BASE_URL}/payment-cancel",
    )

    # ✅ Send email with payment link
    send_payment_email_task.delay(employer.email, checkout_session.url, employer.name)

    # ✅ Update request status
    employer_request.status = "approved"
    employer_request.save()

    messages.success(request, f"Employer {employer.name} approved successfully.")
    return redirect("/admin/user/employerrequest/")


@login_required
def reject_employer(request, pk):
    employer_request = get_object_or_404(EmployerRequest, pk=pk)

    if employer_request.status != "pending":
        messages.warning(request, "This request has already been processed.")
        return redirect("/admin/user/employerrequest/")

    # ✅ Mark request as rejected
    employer_request.status = "rejected"
    employer_request.save()

    messages.error(request, f"Employer request for {employer_request.name} has been rejected.")
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
        return HttpResponse(f"✅ Twilio subaccount {subaccount_sid} closed successfully.", status=200)
    
    except Exception as e:
        return HttpResponse(f"❌ Error closing Twilio subaccount: {str(e)}", status=500)