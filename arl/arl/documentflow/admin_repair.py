from arl.documentflow.models import SentDocuSignEnvelope, SentDocuSignRecipient


def upsert_envelope(
    *,
    envelope_id: str,
    user,
    employer,
    flow,
    flow_step,
    template,
    status: str,
):
    sent_env, _ = SentDocuSignEnvelope.objects.get_or_create(
        envelope_id=envelope_id,
        defaults={
            "user": user,
            "employer": employer,
            "flow": flow,
            "flow_step": flow_step,
            "template": template,
            "status": status,
        },
    )

    changed = False

    if sent_env.user_id != user.id:
        sent_env.user = user
        changed = True
    if sent_env.employer_id != employer.id:
        sent_env.employer = employer
        changed = True
    if sent_env.flow_id != flow.id:
        sent_env.flow = flow
        changed = True
    if sent_env.flow_step_id != flow_step.id:
        sent_env.flow_step = flow_step
        changed = True
    if sent_env.template_id != template.id:
        sent_env.template = template
        changed = True
    if sent_env.status != status:
        sent_env.status = status
        changed = True

    if changed:
        sent_env.save()

    return sent_env


def upsert_recipient(
    *,
    sent_envelope,
    recipient_id: str,
    role_name: str,
    name: str,
    email: str,
    routing_order: int,
    status: str,
):
    recipient, _ = SentDocuSignRecipient.objects.update_or_create(
        sent_envelope=sent_envelope,
        recipient_id=recipient_id,
        defaults={
            "recipient_id_guid": "",
            "role_name": role_name,
            "name": name,
            "email": email,
            "routing_order": routing_order,
            "status": status,
        },
    )
    return recipient


def repair_flow_step(
    *,
    user,
    flow,
    step,
    employee_status="",
    manager_status="",
    manager_name="",
    manager_email="",
):
    employer = user.employer
    template = step.template

    if not employee_status and not manager_status:
        return None

    overall_status = (
        "completed"
        if employee_status == "completed"
        and (
            not manager_status or manager_status == "completed"
        )
        else "sent"
    )

    envelope_id = f"admin-repair-flow-{flow.id}-step-{step.id}-user-{user.id}"

    sent_env = upsert_envelope(
        envelope_id=envelope_id,
        user=user,
        employer=employer,
        flow=flow,
        flow_step=step,
        template=template,
        status=overall_status,
    )

    if employee_status:
        upsert_recipient(
            sent_envelope=sent_env,
            recipient_id="1",
            role_name="GSA",
            name=user.get_full_name() or user.username or user.email,
            email=user.email,
            routing_order=1,
            status=employee_status,
        )

    if manager_status and manager_name and manager_email:
        upsert_recipient(
            sent_envelope=sent_env,
            recipient_id="2",
            role_name="Manager",
            name=manager_name,
            email=manager_email,
            routing_order=2,
            status=manager_status,
        )

    return sent_env