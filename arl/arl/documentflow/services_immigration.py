from datetime import date
from django.db.models import Q


def _get_sin_value(user):
    """
    Returns digits only from decrypted SIN.
    Legacy raw `sin` field is ignored.
    """
    raw = user.sin_plain or ""
    return "".join(ch for ch in str(raw) if ch.isdigit())


def _days_until(target_date):
    if not target_date:
        return None
    return (target_date - date.today()).days


def _sin_status(user):
    sin_value = _get_sin_value(user)

    if not sin_value:
        return {
            "code": "missing",
            "label": "Missing SIN",
            "pill_class": "danger",
            "is_temporary": False,
            "expiry": None,
            "days_left": None,
        }

    # TEMPORARY SIN (starts with 9)
    if sin_value.startswith("9"):
        sin_expiry = getattr(user, "sin_expiration_date", None)
        days_left = _days_until(sin_expiry)

        if not sin_expiry:
            return {
                "code": "missing_expiry",
                "label": "Temporary SIN",
                "pill_class": "warning",
                "is_temporary": True,
                "expiry": sin_expiry,
                "days_left": days_left,
            }

        if days_left is not None and days_left < 0:
            return {
                "code": "expired",
                "label": "Temporary SIN Expired",
                "pill_class": "danger",
                "is_temporary": True,
                "expiry": sin_expiry,
                "days_left": days_left,
            }

        if days_left is not None and days_left <= 120:
            return {
                "code": "expiring_soon",
                "label": "Temporary SIN",
                "pill_class": "warning",
                "is_temporary": True,
                "expiry": sin_expiry,
                "days_left": days_left,
            }

        return {
            "code": "temporary",
            "label": "Temporary SIN",
            "pill_class": "warning",
            "is_temporary": True,
            "expiry": sin_expiry,
            "days_left": days_left,
        }

    # PERMANENT SIN (everything else)
    return {
        "code": "permanent",
        "label": "Permanent SIN",
        "pill_class": "success",
        "is_temporary": False,
        "expiry": None,
        "days_left": None,
    }


def _permit_status(user, sin_info):
    expiry = getattr(user, "work_permit_expiration_date", None)
    days_left = _days_until(expiry)

    if not sin_info["is_temporary"]:
        return {
            "code": "not_required",
            "label": "Permit Not Required",
            "pill_class": "dark",
            "expiry": expiry,
            "days_left": days_left,
        }

    if not expiry:
        return {
            "code": "missing_expiry",
            "label": "Missing Permit Expiry",
            "pill_class": "danger",
            "expiry": expiry,
            "days_left": days_left,
        }

    if days_left is not None and days_left < 0:
        return {
            "code": "expired",
            "label": "Expired",
            "pill_class": "danger",
            "expiry": expiry,
            "days_left": days_left,
        }

    if days_left is not None and days_left <= 120:
        return {
            "code": "expiring_soon",
            "label": "Expiring Soon",
            "pill_class": "warning",
            "expiry": expiry,
            "days_left": days_left,
        }

    return {
        "code": "valid",
        "label": "Valid",
        "pill_class": "success",
        "expiry": expiry,
        "days_left": days_left,
    }


def _overall_status(sin_info, permit_info):
    if sin_info["code"] in {"missing", "expired", "missing_expiry", "expiring_soon"}:
        if sin_info["code"] in {"expired", "missing_expiry"}:
            return {
                "code": "urgent",
                "label": "Urgent",
                "pill_class": "danger",
            }
        return {
            "code": "expiring_soon",
            "label": "Expiring Soon",
            "pill_class": "warning",
        }

    if permit_info["code"] in {"missing_expiry", "expired"}:
        return {
            "code": "urgent",
            "label": "Urgent",
            "pill_class": "danger",
        }

    if permit_info["code"] == "expiring_soon":
        return {
            "code": "expiring_soon",
            "label": "Expiring Soon",
            "pill_class": "warning",
        }

    return {
        "code": "compliant",
        "label": "Compliant",
        "pill_class": "success",
    }


def build_immigration_audit(employer, search_query="", flagged_only=False):
    employees = (
        employer.customuser_set.filter(is_active=True)
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

    rows = []

    for employee in employees:
        sin_expiry = employee.sin_expiration_date
        sin_days = _days_until(sin_expiry)

        sin_info = _sin_status(employee)

        permit_expiry = employee.work_permit_expiration_date
        permit_days = _days_until(permit_expiry)

        permit_info = _permit_status(employee, sin_info)
        overall = _overall_status(sin_info, permit_info)

        row = {
            "employee": employee,
            "sin_masked": employee.masked_sin(),
            "sin_expiry": sin_expiry,
            "sin_days": sin_days,
            "sin_info": sin_info,
            "permit_expiry": permit_expiry,
            "permit_days": permit_days,
            "permit_info": permit_info,
            "overall_status": overall,
            "is_flagged": overall.get("code") != "compliant",
        }

        if flagged_only and not row["is_flagged"]:
            continue

        rows.append(row)

    return {
        "immigration_rows": rows,
        "immigration_search": search_query,
        "immigration_flagged_only": flagged_only,
    }