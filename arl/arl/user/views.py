import traceback
from django.http import JsonResponse
from phonenumbers import (parse, format_number, is_valid_number,
                          PhoneNumberFormat)
from phonenumbers.phonenumberutil import NumberParseException
from django.conf import settings
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
from arl.dsign.tasks import create_docusign_envelope_task
from arl.msg.helpers import (check_verification_token,
                             request_verification_token)
from arl.msg.tasks import send_sms_task
from celery import chain
from .forms import CustomUserCreationForm, TwoFactorAuthenticationForm
from .models import CustomUser, Employer, Store
from .tasks import (create_newhire_data_email, save_user_to_db,
                    send_newhire_template_email_task)
from arl.msg.helpers import client


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
            print(serialized_data)
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
@receiver(post_save, sender=CustomUser)
def handle_new_hire_registration(sender, instance, created, **kwargs):
    """Handles new hire registration by triggering necessary tasks."""
    if not created:
        return  # Exit early if the user was just updated

    try:
        # ✅ Assign user to "GSA" group
        gsa_group, _ = Group.objects.get_or_create(name="GSA")
        instance.groups.add(gsa_group)

        # ✅ Format phone number (if exists)
        formatted_phone = (
            format_number(instance.phone_number, PhoneNumberFormat.E164)
            if instance.phone_number
            else None
        )

        # ✅ Serialize dates safely (handles None values)
        def serialize_date(date_obj):
            return date_obj.strftime("%Y-%m-%d") if date_obj else None

        # ✅ Prepare DocuSign envelope arguments
        envelope_args = {
            "signer_email": instance.email,
            "signer_name": instance.username,
            "template_id": settings.DOCUSIGN_TEMPLATE_ID,
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

        # ✅ Chain tasks in order of execution
        chain(
            send_newhire_template_email_task.s(
                instance.email, instance.first_name, settings.SENDGRID_NEWHIRE_ID
            ),
            # create_docusign_envelope_task.s(envelope_args),
            create_newhire_data_email.s(email_data).set(immutable=True),
            send_sms_task.s(
                formatted_phone,
                "Welcome Aboard! Thank you for registering. Check your email for a link to DocuSign to complete your new hire file.",
            ).set(immutable=True),
        ).apply_async()

        print("📨 Celery tasks have been chained and dispatched successfully!")

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