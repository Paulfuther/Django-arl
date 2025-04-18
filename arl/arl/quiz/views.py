from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView, UpdateView, View
from django.views.generic.list import ListView
from PIL import Image
from waffle import flag_is_active

from arl.helpers import get_s3_images_for_salt_log, upload_to_linode_object_storage

from .forms import AnswerFormSet, QuestionFormSet, QuizForm, SaltLogForm
from .models import Quiz, SaltLog
from .tasks import generate_salt_log_pdf_task, save_salt_log


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
