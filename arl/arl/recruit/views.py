import logging
import os
import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from phonenumbers import (
    NumberParseException,
    PhoneNumberFormat,
    format_number,
    is_valid_number,
    parse,
)

from arl.bucket.helpers import upload_to_linode_object_storage

from .forms import RecruitApplicantForm
from .models import RecruitApplicant

logger = logging.getLogger(__name__)


def recruit_apply_view(request):
    source = request.GET.get("src") or request.POST.get("source") or "direct"

    if request.method == "POST":
        form = RecruitApplicantForm(request.POST, request.FILES)

        if form.is_valid():
            try:
                applicant = form.save(commit=False)
                applicant.source = source

                uploaded_resume = request.FILES.get("resume")

                if uploaded_resume:
                    applicant.resume_original_name = uploaded_resume.name

                    ext = os.path.splitext(uploaded_resume.name)[1].lower()
                    if ext not in [".pdf", ".doc", ".docx"]:
                        ext = ".pdf"

                    if not applicant.resume_folder:
                        applicant.resume_folder = str(uuid.uuid4())

                    object_key = (
                        f"recruit/resumes/{applicant.resume_folder}/{uuid.uuid4()}{ext}"
                    )

                    # 🔥 Upload to Linode
                    upload_to_linode_object_storage(uploaded_resume, object_key)

                    applicant.resume_object_key = object_key

                # ✅ Save applicant
                applicant.save()

                return redirect("recruit:thank_you")

            except Exception:
                logger.exception("❌ Error saving recruit application")

                # Attach error to form (top-level error box)
                form.add_error(
                    None,
                    "There was a problem submitting your application. Please try again.",
                )

                messages.error(
                    request, "There was a problem submitting your application."
                )

        else:
            messages.error(request, "Please correct the errors below.")

    else:
        form = RecruitApplicantForm()

    context = {
        "form": form,
        "source": source,
    }

    return render(request, "recruit/apply.html", context)


def recruit_thank_you_view(request):
    return render(request, "recruit/thank_you.html")


@login_required
def recruit_applicant_list_view(request):
    applicants = RecruitApplicant.objects.all()
    return render(
        request,
        "recruit/applicant_list.html",
        {"applicants": applicants},
    )


# -- Recruit only phone verification view -- 
def recruit_phone_verify_view(request):
    if request.method != "GET":
        return JsonResponse(
            {"valid": False, "error": "Invalid request method."},
            status=405,
        )

    raw_input = request.GET.get("phone_number", "").strip()

    if not raw_input:
        return JsonResponse(
            {"valid": False, "error": "Phone number is required."},
            status=200,
        )

    try:
        parsed_number = parse(raw_input, "CA")

        if not is_valid_number(parsed_number):
            return JsonResponse(
                {"valid": False, "error": "Invalid or non-existent phone number."},
                status=200,
            )

        formatted_e164 = format_number(parsed_number, PhoneNumberFormat.E164)
        formatted_national = format_number(parsed_number, PhoneNumberFormat.NATIONAL)

        return JsonResponse(
            {
                "valid": True,
                "formatted_phone_number": formatted_e164,
                "national_format": formatted_national,
            },
            status=200,
        )

    except NumberParseException:
        return JsonResponse(
            {"valid": False, "error": "Invalid phone number format."},
            status=200,
        )
