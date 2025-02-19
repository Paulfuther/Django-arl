from .models import CarwashStatus


def calculate_durations(store):
    """
    Calculate durations for open/closed periods of a specific carwash store.
    """
    statuses = store.carwash_statuses.order_by('date_time')
    durations = []
    last_closed = None

    for status in statuses:
        if status.status == "closed":
            last_closed = status  # Store the closed status
        elif status.status == "open" and last_closed:
            duration = status.date_time - last_closed.date_time
            durations.append({
                "closed_at": last_closed.date_time,
                "opened_at": status.date_time,
                "duration_closed": duration,
                "reason": last_closed.reason if last_closed.reason else "No reason provided"  # ✅ Get reason from closed event
            })
            last_closed = None  # Reset after pairing

    return durations