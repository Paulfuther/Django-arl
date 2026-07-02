from django.contrib import admin
from .models import SalesTargetCategory, SalesTargetPeriod, SalesTargetLine
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from django.http import HttpResponse
from openpyxl.styles import Alignment

def export_sales_target_management_report(modeladmin, request, queryset):
    wb = Workbook()
    ws = wb.active
    ws.title = "Management Report"

    for period in queryset:

        # Report title
        ws.append(["Sales Target Management Report"])
        ws["A1"].font = Font(size=16, bold=True)

        # Period information
        ws.append([f"Period: {period.name}"])
        ws["A2"].font = Font(bold=True)

        ws.append([f"Dates: {period.start_date} to {period.end_date}"])
        ws["A3"].font = Font(bold=True)

        ws.append([])

        # Column headings
        headers = [
            "Store",
            "Category",
            "Target Amount",
            "Current Sales",
            "% To Target",
            "Projected Sales",
            "Projected Variance",
            "Required Daily Sales",
            "Status",
        ]

        ws.append(headers)

        header_row = ws.max_row

        for cell in ws[header_row]:
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal="center")

        previous_store = None

        lines = (
            period.target_lines
            .select_related("store", "category", "period")
            .order_by("store_id", "category__name")
        )

        

        for line in lines:

            # Insert a blank row when the store changes
            if previous_store is not None and previous_store != line.store_id:
                ws.append([])

            ws.append([
                str(line.store),
                line.category.name,
                round(float(line.target_amount)),
                round(float(line.current_sales)),
                round(float(line.percent_to_target)),
                round(float(line.projected_sales)),
                round(float(line.projected_variance)),
                round(float(line.required_daily_sales)),
                line.status,
            ])

            previous_store = line.store_id

    # Auto-size columns
    for col in ws.columns:
        max_length = 0
        column_letter = col[0].column_letter

        for cell in col:
            if cell.value:
                max_length = max(max_length, len(str(cell.value)))

        ws.column_dimensions[column_letter].width = min(max_length + 2, 45)

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = (
        'attachment; filename="sales_target_management_report.xlsx"'
    )

    wb.save(response)
    return response



class SalesTargetLineInline(admin.TabularInline):
    model = SalesTargetLine
    extra = 1
    fields = ("store", "category", "target_amount")
    autocomplete_fields = ("store", "category")




@admin.register(SalesTargetPeriod)
class SalesTargetPeriodAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "employer",
        "start_date",
        "end_date",
        "total_target_amount",
    )
    list_filter = ("employer", "start_date", "end_date")
    search_fields = ("name", "employer__name")
    inlines = [SalesTargetLineInline]
    actions = [export_sales_target_management_report]

    def total_target_amount(self, obj):
        return sum(line.target_amount for line in obj.target_lines.all())

    total_target_amount.short_description = "Total Target"


@admin.register(SalesTargetCategory)
class SalesTargetCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "employer", "is_active")
    list_filter = ("employer", "is_active")
    search_fields = ("name", "employer__name")


@admin.register(SalesTargetLine)
class SalesTargetLineAdmin(admin.ModelAdmin):
    list_display = (
        "period",
        "store",
        "category",
        "target_amount",
        "current_sales",
        "formatted_percent_to_target",
        "status",
        "formatted_projected_sales",
        "formatted_projected_variance",
        "formatted_required_daily_sales",
    )
    list_filter = ("period", "store", "category")
    search_fields = (
        "period__name",
        "store__name",
        "category__name",
    )
    fields = (
        "store",
        "category",
        "target_amount",
        "current_sales",
        "last_updated",
    )

    def formatted_percent_to_target(self, obj):
        return f"{obj.percent_to_target:.1f}%"
    formatted_percent_to_target.short_description = "% to Target"


    def formatted_projected_sales(self, obj):
        return f"{obj.projected_sales:,.2f}"
    formatted_projected_sales.short_description = "Projected Sales"


    def formatted_projected_variance(self, obj):
        return f"{obj.projected_variance:,.2f}"
    formatted_projected_variance.short_description = "Projected Variance"


    def formatted_required_daily_sales(self, obj):
        return f"{obj.required_daily_sales:,.2f}"
    formatted_required_daily_sales.short_description = "Required Daily Sales"