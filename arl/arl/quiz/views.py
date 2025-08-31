import os
import uuid
from io import BytesIO

from celery.result import AsyncResult
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Q
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.text import slugify
from django.views.generic import CreateView, UpdateView, View
from django.views.generic.list import ListView
from PIL import Image, ImageFile, ImageOps, UnidentifiedImageError
from waffle import flag_is_active

from arl.helpers import (
    get_s3_images_for_salt_log,
    get_signed_url_for_key,
    upload_to_linode_object_storage,
)

from .forms import (
    AnswerFormSet,
    ChecklistForm,
    ChecklistItemFormSet,
    ChecklistTemplateForm,
    QuestionFormSet,
    QuizForm,
    SaltLogForm,
    TemplateItemFormSet,
)
from .models import Checklist, ChecklistItem, ChecklistTemplate, Quiz, SaltLog
from .tasks import (
    generate_checklist_pdf_task,
    generate_fresh_checklist_pdf,
    generate_salt_log_pdf_task,
    save_salt_log,
)


@login_required
def create_quiz(request):
    if request.method == "POST":
        quiz_form = QuizForm(request.POST)
        question_formset = QuestionFormSet(request.POST, instance=Quiz())

        if quiz_form.is_valid():
            quiz = quiz_form.save()

            # Reinitialize the formset with the saved quiz instance
            question_formset = QuestionFormSet(request.POST, instance=quiz)
            if question_formset.is_valid():
                questions = question_formset.save(commit=False)
                for question in questions:
                    question.quiz = quiz
                    question.save()

                    # Handle the answers for each question
                    answer_formset = AnswerFormSet(
                        request.POST,
                        instance=question,
                        prefix=f"'questions-{question.id}')",
                    )
                    if answer_formset.is_valid():
                        answer_formset.save()
                    else:
                        print(
                            f"Answer formset errors for question{question.id}:",
                            answer_formset.errors,
                        )

                return redirect("quiz_list")
            else:
                print("Question formset errors:", question_formset.errors)
        else:
            print("Quiz form errors:", quiz_form.errors)
    else:
        quiz_form = QuizForm()
        question_formset = QuestionFormSet(instance=Quiz())

    return render(
        request,
        "quiz/create_quiz.html",
        {
            "quiz_form": quiz_form,
            "question_formset": question_formset,
        },
    )


@login_required
# @waffle_flag('quiz')
def quiz_list(request):
    # Check if the 'quiz' feature flag is active
    if not flag_is_active(request, "quiz"):
        # If not active, render the custom 403 error template
        return render(request, "flags/feature_not_available.html", status=403)
    quizzes = Quiz.objects.all()
    return render(request, "quiz/quiz_list.html", {"quizzes": quizzes})


@login_required
def take_quiz(request, quiz_id):
    # Check if the 'quiz' feature flag is active
    if not flag_is_active(request, "quiz"):
        # If not active, render the custom 403 error template

        return render(request, "flags/feature_not_available.html", status=403)
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    questions = quiz.questions.all()

    if request.method == "POST":
        score = 0
        total_questions = questions.count()

        for question in questions:
            selected_answer = request.POST.get(f"question_{question.id}")
            correct_answer = question.answers.filter(is_correct=True).first()

            # Assuming correct_answer.text is either "yes" or "no"
            if correct_answer and selected_answer == correct_answer.text.lower():
                score += 1

        return render(
            request,
            "quiz/quiz_result.html",
            {"quiz": quiz, "score": score, "total_questions": total_questions},
        )

    return render(
        request, "quiz/take_quiz.html", {"quiz": quiz, "questions": questions}
    )


class SaltLogCreateView(LoginRequiredMixin, CreateView):
    model = SaltLog
    form_class = SaltLogForm
    template_name = "quiz/salt_log_form.html"
    success_url = reverse_lazy("home")

    def dispatch(self, request, *args, **kwargs):
        print("Dispatch method called.")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        # Pass the user to the form to initialize certain fields
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get(self, request, *args, **kwargs):
        # Initialize the form with the user instance passed to the form
        form = self.form_class(user=self.request.user)
        return self.render_to_response({"form": form})

    def form_valid(self, form):
        # Set the user and user_employer fields for the form instance
        form.instance.user = self.request.user
        form.instance.user_employer = self.request.user.employer
        print(form.instance.user, form.instance.user_employer)
        # Serialize form data to pass to the Celery task
        form_data = self.serialize_form_data(form.cleaned_data)

        # Trigger the Celery task to save form data
        save_salt_log.delay(**form_data)

        # Show a success message
        messages.success(self.request, "Salt Log Added.")

        return redirect("home")

    def form_invalid(self, form):
        # Render the form again with validation errors
        print(form.errors)
        return self.render_to_response({"form": form})

    def serialize_form_data(self, form_data):
        # Convert ForeignKey fields to their primary key values
        form_data["store"] = (
            form_data["store"].pk
            if "store" in form_data and form_data["store"] is not None
            else None
        )
        form_data["user_employer"] = (
            form_data["user_employer"].pk
            if "user_employer" in form_data and form_data["user_employer"] is not None
            else None
        )
        form_data["user"] = self.request.user.pk  # Add the user's ID for task
        return form_data


class ProcessSaltLogImagesView(LoginRequiredMixin, View):
    login_url = "/login/"

    def post(self, request, *args, **kwargs):
        if request.method == "POST":
            user = request.user  # Authenticated user
            # print(user.employer)
            image_folder = request.POST.get("image_folder")
            print(image_folder)
            employer = user.employer
            # Process the uploaded files here
            uploaded_files = request.FILES.getlist(
                "file"
            )  # 'file' is the field name used by Dropzone
            for uploaded_file in uploaded_files:
                # print(uploaded_file.name)
                file = uploaded_file
                folder_name = f"SALTLOG/{employer}/{image_folder}/"
                filename = uploaded_file.name
                employee_key = "{}/{}".format(folder_name, filename)
                # print(employee_key)
                # Open the uploaded image using Pillow
                image = Image.open(file)
                # Resize the image to a larger thumbnail size, e.g.,
                # 1000x1000 pixels
                thumbnail_size = (1500, 1500)
                image.thumbnail(thumbnail_size, Image.LANCZOS)
                # Resize the image to your desired dimensions (e.g., 1000x1000)
                # resized_image = image.resize((500, 500), Image.LANCZOS)
                # print(image)
                # Save the resized image to a temporary BytesIO object
                temp_buffer = BytesIO()
                image.save(temp_buffer, format="JPEG")
                temp_buffer.seek(0)
                # Upload the resized image to Linode Object Storage
                upload_to_linode_object_storage(temp_buffer, employee_key)
                # Close the temporary buffer
                temp_buffer.close()
                # Process and save the files to the desired location
                # You can use the uploaded_files list to iterate through
                # the files and save them

                # Return a JSON response indicating success
            return JsonResponse({"message": "Files uploaded successfully"})
        else:
            # Handle GET request or other methods
            return JsonResponse({"message": "Invalid request method"})


class SaltLogListView(LoginRequiredMixin, ListView):
    model = SaltLog
    template_name = "quiz/salt_log_list.html"
    context_object_name = "saltlogs"

    def get_queryset(self):
        # Filter salt logs by the current user's employer
        return SaltLog.objects.filter(user_employer=self.request.user.employer)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["defer_render"] = True
        return context


class SaltLogUpdateView(LoginRequiredMixin, UpdateView):
    model = SaltLog
    login_url = "/login/"
    form_class = SaltLogForm
    template_name = "quiz/salt_log_form_update.html"
    success_url = reverse_lazy("salt_log_list")

    def dispatch(self, request, *args, **kwargs):
        try:
            # Your print statement for debugging
            print("Dispatch method called.")
            return super().dispatch(request, *args, **kwargs)
        except Exception as e:
            print(f"Exception occurred: {e}")
            raise

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        user = self.request.user
        employer = user.employer
        existing_images = []

        # Check if image_folder exists and get available images from S3
        if self.object.image_folder:
            existing_images = get_s3_images_for_salt_log(
                self.object.image_folder, user.employer
            )
        print(existing_images)
        form = self.form_class(
            instance=self.object, initial={"existing_images": existing_images}
        )
        form.fields["user_employer"].initial = employer

        return self.render_to_response(
            self.get_context_data(
                form=form, existing_images=existing_images, user_employer=employer
            )
        )

    def form_valid(self, form):
        # print(form)
        form.instance.user_employer = self.request.user.employer
        return super().form_valid(form)

    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["user"] = self.request.user
        return context


# this route is turned off in the urls.


def generate_salt_log_pdf(request):
    # Fetch the SaltLog with incident_id = 1
    incident = get_object_or_404(SaltLog, pk=23)
    images = get_s3_images_for_salt_log(incident.image_folder, incident.user_employer)

    # Attempt to trigger the PDF generation task
    try:
        generate_salt_log_pdf_task.delay(incident.id)
        messages.success(request, "PDF generation task initiated successfully.")
    except Exception as e:
        messages.error(request, f"An error occurred while generating the PDF: {e}")

    context = {
        "incident": incident,
        "images": images,
    }
    return render(request, "quiz/salt_log_form_pdf.html", context)


@receiver(post_save, sender=SaltLog)
def handle_new_incident_form_creation(sender, instance, created, **kwargs):
    if created:
        try:
            generate_salt_log_pdf_task.delay(instance.id)
        except Exception as e:
            print(f"An error occurred: {e}")


@login_required
def template_create(request):
    template = ChecklistTemplate(created_by=request.user)
    if request.method == "POST":
        form = ChecklistTemplateForm(request.POST, instance=template)
        formset = TemplateItemFormSet(request.POST, instance=template)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, "Checklist template created.")
            return redirect("template_detail", pk=template.pk)
    else:
        form = ChecklistTemplateForm(instance=template)
        formset = TemplateItemFormSet(instance=template)
    return render(
        request, "quiz/template_form.html", {"form": form, "formset": formset}
    )


@login_required
def template_edit(request, pk):
    template = get_object_or_404(ChecklistTemplate, pk=pk)
    if request.method == "POST":
        form = ChecklistTemplateForm(request.POST, instance=template)
        formset = TemplateItemFormSet(request.POST, instance=template)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, "Template updated.")
            return redirect("template_detail", pk=template.pk)
    else:
        form = ChecklistTemplateForm(instance=template)
        formset = TemplateItemFormSet(instance=template)
    return render(
        request,
        "quiz/template_form.html",
        {"form": form, "formset": formset, "template": template},
    )


@login_required
def template_detail(request, pk):
    template = get_object_or_404(ChecklistTemplate, pk=pk)
    return render(request, "quiz/template_detail.html", {"template": template})


@login_required
def checklist_from_template(request, template_id):
    template = get_object_or_404(
        ChecklistTemplate.objects.prefetch_related("items"),
        pk=template_id,
        is_active=True,
    )

    if request.method == "POST":
        form = ChecklistForm(
            request.POST, user=request.user
        )  # pass user for store queryset
        if form.is_valid():
            checklist = form.save(commit=False)
            checklist.template = template
            checklist.created_by = request.user
            checklist.status = "draft"
            if not checklist.title:
                checklist.title = template.name
            checklist.save()

            # clone items in order
            t_items = template.items.all().order_by("order", "id")
            ChecklistItem.objects.bulk_create(
                [
                    ChecklistItem(
                        checklist=checklist,
                        template_item=ti,
                        text=ti.text,
                        order=(ti.order or idx),
                    )
                    for idx, ti in enumerate(t_items, start=1)
                ]
            )

            messages.success(request, "Checklist created.")
            return redirect("checklist_edit", slug=checklist.slug)
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        form = ChecklistForm(initial={"title": template.name}, user=request.user)

    return render(
        request,
        "quiz/checklist_from_template.html",  # your template above
        {"template": template, "form": form},
    )


@login_required
def checklist_edit(request, slug):
    checklist = get_object_or_404(
        Checklist.objects.select_related("created_by", "submitted_by"),
        slug=slug,
    )

    if request.method == "POST":
        # Photos are uploaded separately; don't pass request.FILES here.
        form = ChecklistForm(request.POST, instance=checklist)
        formset = ChecklistItemFormSet(request.POST, instance=checklist)

        if form.is_valid() and formset.is_valid():
            # Backfill order for any rows that didn't post it
            next_pos = 0
            for fr in formset.forms:
                cd = getattr(fr, "cleaned_data", {}) or {}
                if cd.get("DELETE"):
                    continue
                # if no order provided, assign sequentially
                if not cd.get("order"):
                    fr.instance.order = next_pos
                next_pos += 1

            form.save()
            formset.save()

            action = request.POST.get("action")
            if action == "submit":
                checklist.status = "submitted"
                checklist.submitted_by = request.user
                checklist.submitted_at = timezone.now()
                checklist.save(update_fields=["status", "submitted_by", "submitted_at"])
                # 🔔 Kick off async PDF generation
                try:
                    generate_checklist_pdf_task.delay(checklist.id)
                    messages.success(
                        request, "Checklist submitted. PDF generation started."
                    )
                except Exception as e:
                    messages.error(
                        request,
                        f"Checklist submitted, but PDF task failed to queue: {e}",
                    )

                return redirect("checklist_dashboard")
            else:
                messages.success(request, "Draft saved.")
                return redirect("checklist_edit", slug=checklist.slug)

        # INVALID: dump errors to terminal and fall through to re-render bound forms
        print("Form errors:", form.errors.as_json())
        print("Form non-field errors:", form.non_field_errors())
        print("Formset non-form errors:", formset.non_form_errors())
        for i, fr in enumerate(formset.forms):
            if fr.errors:
                print(f"Item {i} field errors:", fr.errors.as_json())
            nfe = fr.non_field_errors()
            if nfe:
                print(f"Item {i} non-field errors:", nfe)

        messages.error(request, "There are errors in the form. Please review below.")

    else:
        form = ChecklistForm(instance=checklist, user=request.user)
        formset = ChecklistItemFormSet(instance=checklist)

    # Annotate thumbnails (works for GET and invalid POST re-render)
    employer = getattr(request.user, "employer", "noemployer")
    for fr in formset.forms:
        item = fr.instance
        item.signed_url = None  # default
        if (
            getattr(item, "pk", None)
            and getattr(item, "photo", None)
            and item.photo.name
        ):
            # short-lived is fine for the edit page
            item.signed_url = get_signed_url_for_key(item.photo.name, expires_in=900)

    return render(
        request,
        "quiz/checklist_edit.html",
        {"checklist": checklist, "form": form, "formset": formset},
    )


@login_required
def checklist_detail(request, slug):
    checklist = get_object_or_404(
        Checklist.objects.select_related("created_by", "submitted_by", "store"),
        slug=slug,
    )

    qs = (
        ChecklistItem.objects.filter(checklist=checklist)
        .only("text", "result", "comment", "photo", "uuid", "order")
        .order_by("order", "id")
    )

    items = []
    for it in qs:
        signed = None
        if it.photo and it.photo.name:
            # fast: sign key, no listing
            signed = get_signed_url_for_key(it.photo.name, expires_in=900)
        items.append(
            {
                "text": it.text,
                "result": it.result,
                "comment": it.comment,
                "signed_url": signed,
            }
        )

    pdf_url = None
    if getattr(checklist, "pdf_key", ""):
        # If you have a function to turn your Dropbox path into a shareable URL, use it here.
        # pdf_url = dropbox_shared_link_for_path(checklist.pdf_key)
        pdf_url = None  # or keep None and the button will show "not ready"

    return render(
        request,
        "quiz/checklist_detail.html",
        {
            "checklist": checklist,
            "items": items,
            "pdf_url": pdf_url,
        },
    )


@login_required
def checklist_list(request):
    """
    Lists available checklists with quick filters and a link to resume/complete.
    """
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()  # draft|submitted|completed
    mine = request.GET.get("mine")

    qs = Checklist.objects.select_related("created_by", "submitted_by").order_by(
        "-created_at"
    )

    # Common quick filters (tweak to your multi-tenant/employer scoping as needed)
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(notes__icontains=q))
    if status in {"draft", "submitted", "completed"}:
        qs = qs.filter(status=status)
    if mine == "1":
        qs = qs.filter(created_by=request.user)

    paginator = Paginator(qs, 20)
    page = request.GET.get("page")
    page_obj = paginator.get_page(page)

    return render(
        request,
        "quiz/checklist_list.html",
        {
            "page_obj": page_obj,
            "q": q,
            "status": status,
            "mine": mine,
        },
    )


@login_required
def checklist_edit_by_id(request, pk: int):
    """
    Compatibility shim: if someone hits /checklists/<pk>/edit/,
    redirect to the canonical slug URL.
    """
    checklist = get_object_or_404(Checklist, pk=pk)
    return redirect("checklist_edit", slug=checklist.slug)


@login_required
def checklist_dashboard(request):
    """
    Dashboard with: available templates, in-progress (draft), and submitted.
    """
    q = (request.GET.get("q") or "").strip()
    mine = request.GET.get("mine") == "1"

    templates = ChecklistTemplate.objects.filter(is_active=True)
    if q:
        templates = templates.filter(Q(name__icontains=q) | Q(description__icontains=q))
    templates = templates.order_by("name").prefetch_related("items")

    drafts = Checklist.objects.filter(status="draft")
    submitted = Checklist.objects.filter(status="submitted")
    # If you want to show completed too, uncomment:
    # completed = Checklist.objects.filter(status="completed")

    if q:
        drafts = drafts.filter(Q(title__icontains=q) | Q(notes__icontains=q))
        submitted = submitted.filter(Q(title__icontains=q) | Q(notes__icontains=q))
        # completed = completed.filter(Q(title__icontains=q) | Q(notes__icontains=q))

    if mine:
        drafts = drafts.filter(created_by=request.user)
        submitted = submitted.filter(
            Q(created_by=request.user) | Q(submitted_by=request.user)
        )
        # completed = completed.filter(Q(created_by=request.user) | Q(submitted_by=request.user))

    drafts = drafts.select_related("created_by").order_by("-created_at")
    submitted = submitted.select_related("submitted_by").order_by(
        "-submitted_at", "-created_at"
    )
    # completed = completed.order_by("-submitted_at", "-created_at")

    ctx = {
        "q": q,
        "mine": "1" if mine else "",
        "templates": templates,
        "drafts": drafts,
        "submitted": submitted,
        # "completed": completed,
    }
    return render(request, "quiz/checklist_dashboard.html", ctx)


# Allow loading truncated streams (common from mobile)
ImageFile.LOAD_TRUNCATED_IMAGES = True
# Optional: cap max pixels to prevent decompression bombs (18MP ~ 5184x3456)
Image.MAX_IMAGE_PIXELS = 50_000_000

ALLOWED_CT = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/gif",
    "image/heic",
    "image/heif",
    "image/tiff",
    "image/webp",
    "application/octet-stream",  # many Android browsers use this
    None,  # some clients omit CT
}

MAX_BYTES = 10 * 1024 * 1024  # 10MB


class UploadChecklistItemPhotoView(LoginRequiredMixin, View):
    login_url = "/login/"

    def post(self, request, slug, item_uuid):
        file = request.FILES.get("file")
        if not file:
            return JsonResponse({"error": "No file provided"}, status=400)

        # (Optional) multi-tenant safety: ensure checklist belongs to user's employer
        checklist = get_object_or_404(Checklist, slug=slug)
        item = get_object_or_404(ChecklistItem, checklist=checklist, uuid=item_uuid)

        # Quick size guard (cheap)
        if getattr(file, "size", 0) > MAX_BYTES:
            return JsonResponse({"error": "File too large (max 10MB)."}, status=400)

        # Content-type (defensive; we'll still try to decode)
        ct = getattr(file, "content_type", None)
        if ct not in ALLOWED_CT:
            return JsonResponse({"error": f"Unsupported type: {ct}"}, status=400)

        try:
            # ---- Decode + normalize (HEIC works if pillow-heif is registered) ----
            # Make sure you have run:  from pillow_heif import register_heif_opener; register_heif_opener()
            # (do this once at app startup)
            img = Image.open(file)

            # Correct orientation from EXIF, ignore if missing
            try:
                img = ImageOps.exif_transpose(img)
            except Exception:
                pass

            # Normalize color mode (drop alpha)
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")

            # Resize to a sane maximum for your app
            img.thumbnail((1500, 1500), Image.LANCZOS)

            # ---- Build storage key ----
            employer_segment = slugify(
                str(getattr(request.user, "employer", "noemployer"))
            )
            base, _ = os.path.splitext(file.name)
            filename = f"{slugify(base) or 'photo'}-{uuid.uuid4().hex[:8]}.jpg"
            key = (
                f"CHECKLISTS/{employer_segment}/{checklist.slug}/{item.uuid}/{filename}"
            )

            # ---- Encode JPEG + upload ----
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=85, optimize=True)
            buf.seek(0)
            upload_to_linode_object_storage(buf, key)
            buf.close()

            # ---- Persist and return signed URL ----
            item.photo.name = key
            item.save(update_fields=["photo"])

            signed_url = get_signed_url_for_key(key, expires_in=3600)
            return JsonResponse({"message": "ok", "key": key, "url": signed_url})

        except UnidentifiedImageError:
            return JsonResponse({"error": "Unreadable image file."}, status=400)
        except Image.DecompressionBombError:
            return JsonResponse(
                {"error": "Image too large (pixel dimensions)."}, status=400
            )
        except Exception as e:
            return JsonResponse({"error": f"Upload failed: {e}"}, status=500)


@login_required
def checklist_download_fresh_start_api(request, slug):
    checklist = get_object_or_404(Checklist, slug=slug)
    async_res = generate_fresh_checklist_pdf.delay(checklist.id)
    return JsonResponse({"task_id": async_res.id})


@login_required
def checklist_download_fresh_status(request):
    task_id = request.GET.get("task_id")
    if not task_id:
        return HttpResponseBadRequest("Missing task_id")

    res = AsyncResult(task_id)
    if not res.ready():
        return JsonResponse({"ready": False}, status=202)

    if res.failed():
        # show the actual exception message from the task
        return JsonResponse(
            {"ready": True, "error": str(res.info) or "PDF generation failed"},
            status=200,
        )

    key = res.result  # object key returned by the task
    url = get_signed_url_for_key(key, expires_in=120)
    return JsonResponse({"ready": True, "url": url}, status=200)


@login_required
def checklist_report_html(request, slug):
    """
    Render the checklist report HTML (same context as the PDF) directly in the browser.
    Useful for debugging layout/styles without generating a PDF.
    """
    checklist = (
        Checklist.objects.select_related("created_by", "submitted_by", "store")
        .prefetch_related("items")
        .get(slug=slug)
    )
    print("checklist store :", checklist.store)
    # Build items with short-lived signed URLs (so images load in browser)
    items = []
    for it in checklist.items.all().order_by("order", "id"):
        photo_url = None
        if it.photo and it.photo.name:
            photo_url = get_signed_url_for_key(it.photo.name, expires_in=900)
        items.append(
            {
                "text": it.text,
                "result": it.result,
                "comment": it.comment,
                "photo_url": photo_url,
            }
        )

    ctx = {
        "checklist": checklist,
        "items": items,
        "store_number": getattr(checklist.store, "number", None),
        "store_name": getattr(checklist.store, "name", None),
    }
    # Reuse the exact same template as the PDF:
    return render(request, "quiz/checklist_pdf_for_app.html", ctx)
