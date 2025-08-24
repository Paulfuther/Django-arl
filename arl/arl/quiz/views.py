import os
import uuid
from io import BytesIO

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
from PIL import Image, ImageOps
from waffle import flag_is_active

from arl.helpers import (
    get_s3_image_for_checklist_item,
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
from .tasks import generate_salt_log_pdf_task, save_salt_log, generate_checklist_pdf_task


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
    template = get_object_or_404(ChecklistTemplate, pk=template_id, is_active=True)
    if request.method == "POST":
        # create Checklist + its items from the template
        title = request.POST.get("title") or template.name
        checklist = Checklist.objects.create(
            template=template, title=title, created_by=request.user
        )
        bulk_items = []
        for order, ti in enumerate(template.items.all(), start=1):
            bulk_items.append(
                ChecklistItem(
                    checklist=checklist,
                    template_item=ti,
                    text=ti.text,
                    order=order,
                )
            )
        ChecklistItem.objects.bulk_create(bulk_items)
        messages.success(request, "Checklist started.")
        return redirect("checklist_edit", slug=checklist.slug)

    return render(request, "quiz/checklist_from_template.html", {"template": template})


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
                    messages.success(request, "Checklist submitted. PDF generation started.")
                except Exception as e:
                    messages.error(request, f"Checklist submitted, but PDF task failed to queue: {e}")

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
        if getattr(item, "pk", None):
            if item.photo and item.photo.name:
                item.signed_url = get_signed_url_for_key(item.photo.name)
            else:
                item.signed_url = get_s3_image_for_checklist_item(
                    checklist.slug, str(item.uuid), employer
                )

    return render(
        request,
        "quiz/checklist_edit.html",
        {"checklist": checklist, "form": form, "formset": formset},
    )


@login_required
def checklist_detail(request, slug):
    checklist = get_object_or_404(Checklist, slug=slug)
    return render(request, "quiz/checklist_detail.html", {"checklist": checklist})


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


ACCEPTED_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_BYTES = 10 * 1024 * 1024  # 10 MB per file, align with your quick email rules


class UploadChecklistItemPhotoView(LoginRequiredMixin, View):
    login_url = "/login/"

    def post(self, request, slug, item_uuid):
        if "file" not in request.FILES:
            return HttpResponseBadRequest("No file")

        checklist = get_object_or_404(Checklist, slug=slug)
        item = get_object_or_404(ChecklistItem, checklist=checklist, uuid=item_uuid)

        f = request.FILES["file"]

        # Open/normalize/resize
        img = Image.open(f)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        try:
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass
        img.thumbnail((1500, 1500), Image.LANCZOS)

        # Build key
        employer_segment = str(getattr(request.user, "employer", "noemployer"))
        base, _ = os.path.splitext(f.name)
        filename = f"{slugify(base) or 'photo'}-{uuid.uuid4().hex[:8]}.jpg"
        key = f"CHECKLISTS/{employer_segment}/{checklist.slug}/{item.uuid}/{filename}"

        # Upload
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=85, optimize=True)
        buf.seek(0)
        upload_to_linode_object_storage(buf, key)
        buf.close()

        # Persist on the model
        item.photo.name = key
        item.save(update_fields=["photo"])

        # Return a signed URL (so the client shows it only AFTER upload)
        signed_url = get_signed_url_for_key(key, expires_in=3600)
        return JsonResponse({"message": "ok", "key": key, "url": signed_url})