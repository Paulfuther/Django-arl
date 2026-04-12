from collections import defaultdict

from django.db.models import Q

from arl.documentflow.models import DocumentFlow, SentDocuSignEnvelope
from arl.dsign.models import ProcessedDocsignDocument, SignedDocumentFile
from arl.user.models import CustomUser


def normalize_template_name(value):
    return (value or "").strip().lower()


def build_document_audit(employer, search_query="", incomplete_only=False):
    flow = (
        DocumentFlow.objects.filter(employer=employer, is_active=True, is_default=True)
        .prefetch_related("steps__template")
        .first()
    )

    employees = (
        CustomUser.objects.filter(employer=employer, is_active=True)
        .select_related("store")
        .order_by("-date_joined")
    )

    search_query = (search_query or "").strip()
    if search_query:
        employees = employees.filter(
            Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
            | Q(email__icontains=search_query)
        )

    if not flow:
        return {
            "flow": None,
            "steps": [],
            "rows": [],
            "audit_search": search_query,
            "audit_incomplete_only": incomplete_only,
        }

    steps = list(
        flow.steps.filter(is_active=True)
        .select_related("template")
        .order_by("step_order", "id")
    )

    employee_ids = list(employees.values_list("id", flat=True))

    signed_docs = (
        SignedDocumentFile.objects.filter(employer=employer, user_id__in=employee_ids)
        .select_related("user")
        .only(
            "id",
            "user_id",
            "template_name",
            "document_title",
            "uploaded_at",
            "file_name",
        )
        .order_by("-uploaded_at")
    )

    processed_docs = (
        ProcessedDocsignDocument.objects.filter(
            employer=employer, user_id__in=employee_ids
        )
        .only("id", "user_id", "template_name", "envelope_id")
        .order_by("-id")
    )

    sent_envelopes = (
        SentDocuSignEnvelope.objects.filter(
            employer=employer,
            user_id__in=employee_ids,
            flow=flow,
        )
        .select_related("flow_step", "template", "user")
        .order_by("-sent_at")
    )

    docs_by_user = defaultdict(list)
    for doc in signed_docs:
        docs_by_user[doc.user_id].append(doc)

    processed_by_user = defaultdict(list)
    for doc in processed_docs:
        processed_by_user[doc.user_id].append(doc)

    envelopes_by_user_step = {}
    for env in sent_envelopes:
        if env.flow_step_id:
            key = (env.user_id, env.flow_step_id)
            if key not in envelopes_by_user_step:
                envelopes_by_user_step[key] = env

    rows = []

    for employee in employees:
        employee_docs = docs_by_user.get(employee.id, [])
        employee_processed = processed_by_user.get(employee.id, [])

        step_results = []
        completed_count = 0

        for step in steps:
            template = getattr(step, "template", None)
            required_name = normalize_template_name(
                getattr(template, "template_name", None)
                or getattr(template, "name", None)
                or step.label
                or ""
            )

            matched_doc = None
            matched_processed = None
            matched_env = envelopes_by_user_step.get((employee.id, step.id))

            if required_name:
                for doc in employee_docs:
                    template_name = normalize_template_name(doc.template_name)
                    document_title = normalize_template_name(doc.document_title)
                    file_name = normalize_template_name(doc.file_name)

                    if (
                        template_name == required_name
                        or document_title == required_name
                        or required_name in file_name
                    ):
                        matched_doc = doc
                        break

                if not matched_doc:
                    for proc in employee_processed:
                        proc_template_name = normalize_template_name(proc.template_name)
                        if proc_template_name == required_name:
                            matched_processed = proc
                            break

            # Status priority
            if matched_doc:
                status = "completed"
                completed_at = matched_doc.uploaded_at
            elif matched_env and matched_env.status == "completed":
                status = "completed"
                completed_at = matched_env.completed_at
            elif matched_processed:
                status = "completed"
                completed_at = None
            elif matched_env:
                status = matched_env.status or "sent"
                completed_at = None
            else:
                status = "not_sent"
                completed_at = None

            if status == "completed":
                completed_count += 1

            step_results.append(
                {
                    "step": step,
                    "template": template,
                    "required_name": required_name,
                    "status": status,
                    "is_complete": status == "completed",
                    "matched_doc": matched_doc,
                    "matched_processed": matched_processed,
                    "matched_env": matched_env,
                    "completed_at": completed_at,
                }
            )

        total_required = len(steps)
        is_fully_complete = total_required > 0 and completed_count == total_required

        if total_required == 0:
            overall_status = "no_docs"
        elif is_fully_complete:
            overall_status = "completed"
        elif completed_count > 0:
            overall_status = "in_progress"
        elif any(
            item["status"] in ["sent", "delivered", "declined", "voided"]
            for item in step_results
        ):
            overall_status = "in_progress"
        else:
            overall_status = "not_sent"

        row = {
            "employee": employee,
            "store": getattr(employee, "store", None),
            "step_results": step_results,
            "completed_count": completed_count,
            "total_required": total_required,
            "is_complete": is_fully_complete,
            "is_incomplete": not is_fully_complete,
            "overall_status": overall_status,
        }

        if incomplete_only and is_fully_complete:
            continue

        rows.append(row)
    print(
        "flow: ",
        flow,
        "steps :",
        steps,
        "rows : ",
        rows,
        "audit_search :",
        search_query,
        "audit_incomplete_only :",
        incomplete_only,
    )
    return {
        "flow": flow,
        "steps": steps,
        "rows": rows,
        "audit_search": search_query,
        "audit_incomplete_only": incomplete_only,
    }
