from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from .services import build_document_audit


@login_required
def document_audit_log_partial(request):
    employer = getattr(request.user, "employer", None)
    if not employer:
        return redirect("home")

    context = build_document_audit(employer)
    return render(
        request,
        "documentflow/partials/document_audit_log.html",
        context,
    )

