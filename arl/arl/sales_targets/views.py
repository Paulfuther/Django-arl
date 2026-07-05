from collections import defaultdict
from decimal import Decimal

from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render

from .models import SalesTargetLine, SalesTargetPeriod


def index(request):
    return HttpResponse("Sales targets app is working.")


def sales_target_dashboard(request, period_id):
    period = get_object_or_404(SalesTargetPeriod, id=period_id)

    lines = (
        SalesTargetLine.objects.filter(period=period)
        .select_related("store", "category")
        .order_by("store__number", "category__name")
    )

    total_target = Decimal("0")
    total_current = Decimal("0")
    total_projected = Decimal("0")

    needs_attention = []

    category_totals = defaultdict(
        lambda: {
            "target": Decimal("0"),
            "current": Decimal("0"),
            "projected": Decimal("0"),
        }
    )

    for line in lines:
        total_target += line.target_amount
        total_current += line.current_sales
        total_projected += line.projected_sales

        category_name = line.category.name
        category_totals[category_name]["target"] += line.target_amount
        category_totals[category_name]["current"] += line.current_sales
        category_totals[category_name]["projected"] += line.projected_sales

        if line.projected_variance < 0:
            needs_attention.append(
                {
                    "store": line.store.number,
                    "category": line.category.name,
                    "variance": line.projected_variance,
                    "required_daily_sales": line.required_daily_sales,
                    "status": line.status,
                }
            )

    projected_variance = total_projected - total_target

    category_summary = []

    for category, totals in category_totals.items():
        variance = totals["projected"] - totals["target"]

        if variance > 0:
            status = "🟢 Ahead"
        elif variance >= -(totals["target"] * Decimal("0.05")):
            status = "🟡 On Track"
        else:
            status = "🔴 Behind"

        category_summary.append(
            {
                "category": category,
                "target": totals["target"],
                "current": totals["current"],
                "projected": totals["projected"],
                "variance": variance,
                "status": status,
            }
        )

    needs_attention = sorted(needs_attention, key=lambda x: x["variance"])[:10]

    category_summary = sorted(category_summary, key=lambda x: x["variance"])

    context = {
        "period": period,
        "total_target": total_target,
        "total_current": total_current,
        "total_projected": total_projected,
        "projected_variance": projected_variance,
        "needs_attention": needs_attention,
        "category_summary": category_summary,
    }

    return render(
        request,
        "sales_targets/dashboard.html",
        context,
    )
