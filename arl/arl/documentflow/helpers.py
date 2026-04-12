from .models import DocumentFlow


def get_default_document_flow(employer):
    return (
        DocumentFlow.objects.filter(employer=employer, is_active=True, is_default=True)
        .prefetch_related("steps__template")
        .first()
    )


def get_first_flow_step(flow):
    if not flow:
        return None
    return flow.steps.filter(is_active=True).order_by("step_order").first()


def get_next_flow_step(flow, current_step_order):
    return (
        flow.steps.filter(is_active=True, step_order__gt=current_step_order)
        .order_by("step_order")
        .first()
    )