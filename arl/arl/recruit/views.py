import os
import uuid

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from arl.bucket.helpers import upload_to_linode_object_storage

from .forms import RecruitApplicantForm
from .models import RecruitApplicant


def recruit_apply_view(request):
    source = request.GET.get("src") or request.POST.get("source") or "direct"

    if request.method == "POST":
        form = RecruitApplicantForm(request.POST, request.FILES)
        if form.is_valid():
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

                upload_to_linode_object_storage(uploaded_resume, object_key)
                applicant.resume_object_key = object_key

            applicant.save()
            return redirect("recruit:thank_you")
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
