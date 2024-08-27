from django.shortcuts import render, redirect, get_object_or_404
from .forms import QuizForm, QuestionFormSet, AnswerFormSet
from .models import Quiz
from django.contrib.auth.decorators import login_required


@login_required
def create_quiz(request):
    if request.method == 'POST':
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
                    answer_formset = AnswerFormSet(request.POST,
                                                   instance=question,
                                                   prefix=f"'questions-"
                                                   f"{question.id}')")
                    if answer_formset.is_valid():
                        answer_formset.save()
                    else:
                        print(f"Answer formset errors for question"
                              f"{question.id}:", answer_formset.errors)

                return redirect('quiz_list')
            else:
                print("Question formset errors:", question_formset.errors)
        else:
            print("Quiz form errors:", quiz_form.errors)
    else:
        quiz_form = QuizForm()
        question_formset = QuestionFormSet(instance=Quiz())

    return render(request, 'quiz/create_quiz.html', {
        'quiz_form': quiz_form,
        'question_formset': question_formset,
    })


@login_required
def quiz_list(request):
    quizzes = Quiz.objects.all()
    return render(request, 'quiz/quiz_list.html', {'quizzes': quizzes})


@login_required
def take_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    questions = quiz.questions.all()

    if request.method == 'POST':
        score = 0
        total_questions = questions.count()

        for question in questions:
            selected_answer = request.POST.get(f'question_{question.id}')
            correct_answer = question.answers.filter(is_correct=True).first()

            # Assuming correct_answer.text is either "yes" or "no"
            if (correct_answer and selected_answer ==
                    correct_answer.text.lower()):
                score += 1

        return render(request, 'quiz/quiz_result.html', {
            'quiz': quiz,
            'score': score,
            'total_questions': total_questions
        })

    return render(request, 'quiz/take_quiz.html', {
        'quiz': quiz,
        'questions': questions
    })
