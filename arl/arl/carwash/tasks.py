from __future__ import absolute_import, unicode_literals
from collections import defaultdict
from django.utils.timezone import localtime
import json
from collections import Counter
from arl.celery import app
from arl.carwash.models import Store, CarwashStatus


@app.task(name="carwash_closure_report")
def generate_carwash_status_report():
    stores = Store.objects.filter(carwash=True)
    report_data = defaultdict(
        lambda: {
            "stores": [],
            "summary": defaultdict(lambda: {"duration": "0h 0m", "reason": "No data"}),
        }
    )

    for store in stores:
        statuses = (
            CarwashStatus.objects.filter(store=store)
            .order_by("date_time")
            .values("status", "reason", "date_time")
        )

        durations = []
        closed_at = None
        monthly_duration = defaultdict(int)
        monthly_reasons = defaultdict(list)  # ✅ Collect all reasons

        for entry in statuses:
            if entry["status"] == "closed" and not closed_at:
                closed_at = entry["date_time"]  # Store closed time
                reason = entry["reason"] or "No reason provided"  # ✅ Store reason
            elif entry["status"] == "open" and closed_at:
                opened_at = entry["date_time"]  # Store reopened
                duration = opened_at - closed_at

                # Convert to hours and minutes
                duration_hours, remainder = divmod(duration.total_seconds(), 3600)
                duration_minutes = remainder // 60

                month = closed_at.strftime("%Y-%m")  # Extract YYYY-MM

                # ✅ Store reasons associated with this month
                monthly_reasons[month].append(reason)

                durations.append(
                    {
                        "closed_at": localtime(closed_at).strftime("%Y-%m-%d %I:%M %p"),
                        "opened_at": localtime(opened_at).strftime("%Y-%m-%d %I:%M %p"),
                        "duration_closed": f"{int(duration_hours)}h {int(duration_minutes)}m",
                        "reason": reason,
                    }
                )

                monthly_duration[month] += duration.total_seconds()
                closed_at = None  # Reset for next closure

        # Handle stores that are still closed
        if closed_at:
            month = closed_at.strftime("%Y-%m")
            monthly_reasons[month].append("Still closed")

            durations.append(
                {
                    "closed_at": localtime(closed_at).strftime("%Y-%m-%d %I:%M %p"),
                    "opened_at": None,
                    "duration_closed": "Still closed",
                    "reason": "Still closed",
                }
            )

        # ✅ Convert monthly durations to formatted time strings
        formatted_summary = {
            month: {
                "duration": f"{int(seconds // 3600)}h {int((seconds % 3600) // 60)}m",
                "reason": Counter(monthly_reasons[month]).most_common(1)[0][0]
                if monthly_reasons[month]
                else "No data",
            }
            for month, seconds in monthly_duration.items()
        }

        # ✅ Store data under the appropriate month
        for month in formatted_summary.keys():
            report_data[month]["stores"].append(
                {
                    "store_id": store.id,
                    "store_number": store.number,
                    "durations": durations,
                }
            )
            report_data[month]["summary"][store.number] = formatted_summary[month]

    return json.dumps(report_data, default=str)
