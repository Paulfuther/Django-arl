from django.db.models import Q

from arl.user.models import CustomUser
from arl.dsign.models import ProcessedDocsignDocument
from .models import DocumentFlow


def normalize_template_name(value):
    return (value or "").strip().lower()


def build_document_audit(employer, search_query="", incomplete_only=False):
    """
    Build a read-only audit log of:
    - what documents are required by the employer's default flow
    - which of those each employee has signed
    - optional filtering by search and incomplete-only
    """

    flow = (
        DocumentFlow.objects
        .filter(employer=employer, is_active=True, is_default=True)
        .prefetch_related("steps__template")
        .first()
    )

    employees = CustomUser.objects.filter(
        employer=employer,
        is_active=True,
    ).select_related("store")

    search_query = (search_query or "").strip()
    if search_query:
        employees = employees.filter(
            Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
            | Q(email__icontains=search_query)
        )

    employees = employees.order_by("-date_joined")

    if not flow:
        return {
            "flow": None,
            "steps": [],
            "rows": [],
            "audit_search": search_query,
            "audit_incomplete_only": incomplete_only,
        }

    steps = list(flow.steps.all().order_by("step_order"))

    processed_docs = (
        ProcessedDocsignDocument.objects
        .filter(employer=employer, user__in=employees)
        .order_by("-processed_at")
    )

    signed_lookup = {}
    for doc in processed_docs:
        key = (doc.user_id, normalize_template_name(doc.template_name))
        if key not in signed_lookup:
            signed_lookup[key] = doc

    rows = []
    for employee in employees:
        cells = []
        completed_count = 0

        for step in steps:
            template_name = getattr(step.template, "template_name", "")
            key = (employee.id, normalize_template_name(template_name))
            signed_doc = signed_lookup.get(key)
            is_signed = bool(signed_doc)

            if is_signed:
                completed_count += 1

            cells.append({
                "step": step,
                "is_signed": is_signed,
                "signed_doc": signed_doc,
            })

        total_count = len(steps)
        is_complete = total_count > 0 and completed_count == total_count

        if incomplete_only and is_complete:
            continue

        rows.append({
            "employee": employee,
            "cells": cells,
            "completed_count": completed_count,
            "total_count": total_count,
            "is_complete": is_complete,
        })

    rows = sorted(
            rows,
            key=lambda r: (
                r["is_complete"],
                -(r["employee"].date_joined.timestamp() if r["employee"].date_joined else 0),
            ),
        )
    print("flow.  ", flow)
    print("steps.  ", steps)

    return {
        "flow": flow,
        "steps": steps,
        "rows": rows,
        "audit_search": search_query,
        "audit_incomplete_only": incomplete_only,
    }