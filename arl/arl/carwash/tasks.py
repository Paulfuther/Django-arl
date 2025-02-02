from __future__ import absolute_import, unicode_literals
from collections import defaultdict
from arl.celery import app
from arl.carwash.models import Store
from arl.carwash.helpers import calculate_durations  


def format_duration(seconds):
    """Convert seconds into a human-readable format: 'Xh Xm Xs'"""
    if seconds is None:
        return None
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}h {minutes}m {seconds}s".strip()


@app.task(name="carwash_closure_duration_task")
def generate_carwash_status_report():
    """Celery task to generate the carwash status report with monthly summaries."""
    stores = Store.objects.filter(carwash=True)
    report_data = []

    for store in stores:
        durations = calculate_durations(store)  # Get status durations
        monthly_summary = defaultdict(int)  # Dictionary to store total closed time per month
        formatted_durations = []

        for duration in durations:
            closed_seconds = duration["duration_closed"].total_seconds() if duration.get("duration_closed") else 0

            # Format individual durations
            formatted_durations.append({
                "closed_at": duration["closed_at"].isoformat() if duration.get("closed_at") else None,
                "opened_at": duration["opened_at"].isoformat() if duration.get("opened_at") else None,
                "duration_closed": format_duration(closed_seconds),
            })

            # Group by month and sum total closed time
            if duration.get("closed_at"):
                month_key = duration["closed_at"].strftime("%Y-%m")  # Format: YYYY-MM
                monthly_summary[month_key] += closed_seconds

        # Convert monthly summary to formatted strings
        formatted_monthly_summary = {
            month: format_duration(total_seconds)
            for month, total_seconds in monthly_summary.items()
        }

        report_data.append({
            "store_id": store.id,
            "store_number": store.number,
            "durations": formatted_durations,
            "monthly_summary": formatted_monthly_summary,  # Add summary
        })

    return report_data  # JSON serializable