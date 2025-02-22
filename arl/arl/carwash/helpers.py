
def calculate_durations(store):
    """
    Calculate durations for open/closed periods of a specific carwash store.
    """
    statuses = store.carwash_statuses.order_by("date_time")
    durations = []
    last_closed = None

    for status in statuses:
        if status.status == "closed":
            last_closed = status
        elif status.status == "open" and last_closed:
            duration = status.date_time - last_closed.date_time
            durations.append({
                "closed_at": last_closed.date_time,
                "opened_at": status.date_time,
                "duration_closed": duration,
                "reason": status.reason if status.reason else "No reason provided",
                "status": status.status  # ✅ Ensure `status` is added
            })
            last_closed = None

    # ✅ Ensure the latest status is always included
    if statuses.exists():
        last_status = statuses.last()
        durations.append({
            "closed_at": last_status.date_time if last_status.status == "closed" else None,
            "opened_at": last_status.date_time if last_status.status == "open" else None,
            "duration_closed": None,  # No duration for the most recent status
            "reason": last_status.reason if last_status.reason else "No reason provided",
            "status": last_status.status  # ✅ Store the latest status
        })

    return durations