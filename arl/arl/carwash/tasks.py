from __future__ import absolute_import, unicode_literals
from collections import defaultdict
from django.utils.timezone import localtime
import json

from arl.celery import app
from arl.carwash.models import Store, CarwashStatus


@app.task(name="carwash_closure_report")
def generate_carwash_status_report():
    stores = Store.objects.filter(carwash=True)
    report_data = []

    for store in stores:
        statuses = (
            CarwashStatus.objects.filter(store=store)
            .order_by("date_time")
            .values("status", "reason", "date_time")
        )

        durations = []
        closed_at = None
        closure_reason = None
        monthly_summary = defaultdict(int)  # ✅ Track total closed time per month

        for entry in statuses:
            if entry["status"] == "closed" and not closed_at:
                closed_at = entry["date_time"]
                closure_reason = entry["reason"] or "No reason provided"
            elif entry["status"] == "open" and closed_at:
                opened_at = entry["date_time"]
                duration = opened_at - closed_at

                # Convert to hours and minutes
                duration_hours, remainder = divmod(duration.total_seconds(), 3600)
                duration_minutes = remainder // 60
                
                # ✅ Add to monthly summary
                month = closed_at.strftime("%Y-%m")  # Extract YYYY-MM format
                monthly_summary[month] += duration.total_seconds()

                durations.append({
                    "closed_at": localtime(closed_at).strftime("%Y-%m-%d %I:%M %p"),
                    "opened_at": localtime(opened_at).strftime("%Y-%m-%d %I:%M %p"),
                    "duration_closed": f"{int(duration_hours)}h {int(duration_minutes)}m",
                    "reason": closure_reason,
                })
                closed_at = None
                closure_reason = None

        # Handle still closed cases
        if closed_at:
            durations.append({
                "closed_at": localtime(closed_at).strftime("%Y-%m-%d %I:%M %p"),
                "opened_at": None,
                "duration_closed": "Still closed",
                "reason": closure_reason or "Still closed",
            })

        # ✅ Format monthly summary
        formatted_summary = {
            month: f"{int(seconds // 3600)}h {int((seconds % 3600) // 60)}m"
            for month, seconds in monthly_summary.items()
        }

        report_data.append({
            "store_id": store.id,
            "store_number": store.number,
            "durations": durations,
            "monthly_summary": formatted_summary,  # ✅ Include the summary
        })

    return json.dumps(report_data, default=str)