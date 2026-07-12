import uuid
from decimal import ROUND_UP, Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


class SalesTargetCategory(models.Model):
    MEASUREMENT_CHOICES = [
        ("sales", "Dollar Sales"),
        ("units", "Units Sold"),
    ]
    employer = models.ForeignKey(
        "user.Employer",  # Change if your Employer model is elsewhere
        on_delete=models.CASCADE,
        related_name="sales_target_categories",
    )

    name = models.CharField(max_length=100)
    measurement_type = models.CharField(
        max_length=20,
        choices=MEASUREMENT_CHOICES,
        default="sales",
    )

    d365_category_code = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text=("Category code from the D365 Category Sales Report. Example: 2310"),
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "employer",
                    "d365_category_code",
                ],
                condition=(
                    Q(d365_category_code__isnull=False) & ~Q(d365_category_code="")
                ),
                name="unique_d365_code_per_employer",
            ),
        ]

    def __str__(self):
        return self.name


class SalesTargetPeriod(models.Model):
    employer = models.ForeignKey(
        "user.Employer",
        on_delete=models.CASCADE,
        related_name="sales_target_periods",
    )
    name = models.CharField(max_length=150)
    start_date = models.DateField()
    end_date = models.DateField()
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-start_date"]
        verbose_name = "Sales Target Period"
        verbose_name_plural = "Sales Target Periods"

    def clean(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError("End date cannot be before start date.")

    def __str__(self):
        return f"{self.employer} - {self.name}"


class SalesTargetLine(models.Model):
    period = models.ForeignKey(
        SalesTargetPeriod,
        on_delete=models.CASCADE,
        related_name="target_lines",
    )
    store = models.ForeignKey(
        "user.Store",
        on_delete=models.CASCADE,
        related_name="sales_target_lines",
        null=True,
        blank=True,
    )
    category = models.ForeignKey(
        SalesTargetCategory,
        on_delete=models.PROTECT,
        related_name="target_lines",
    )
    target_amount = models.DecimalField(max_digits=12, decimal_places=2)

    current_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    current_units = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("period", "store", "category")
        ordering = ["store_id", "category__name"]

    def clean(self):
        if self.period and self.category:
            if self.period.employer_id != self.category.employer_id:
                raise ValidationError(
                    "Target category must belong to the same employer as the target period."
                )

        if self.period and self.store:
            if self.period.employer_id != self.store.employer_id:
                raise ValidationError(
                    "Store must belong to the same employer as the target period."
                )

    @property
    def total_days(self):
        return max((self.period.end_date - self.period.start_date).days + 1, 1)

    @property
    def elapsed_days(self):
        today = timezone.localdate()

        if today < self.period.start_date:
            return 0

        if today > self.period.end_date:
            return self.total_days

        return (today - self.period.start_date).days + 1

    @property
    def remaining_days(self):
        return max(self.total_days - self.elapsed_days, 0)

    @property
    def percent_time_elapsed(self):
        if self.total_days == 0:
            return Decimal("0")

        return Decimal(self.elapsed_days) / Decimal(self.total_days) * Decimal("100")

    @property
    def percent_to_target(self):
        if not self.target_amount:
            return Decimal("0")

        return (
            self.current_value
            / self.target_amount
            * Decimal("100")
        )

    @property
    def projected_sales(self):
        if self.elapsed_days == 0:
            return Decimal("0")

        daily_average = (
            self.current_value
            / Decimal(self.elapsed_days)
        )

        return daily_average * Decimal(self.total_days)

    @property
    def projected_variance(self):
        return self.projected_sales - self.target_amount

    @property
    def remaining_sales_needed(self):
        return max(
            self.target_amount - self.current_value,
            Decimal("0"),
        )

    @property
    def required_daily_sales(self):
        if self.remaining_days == 0:
            return 1

        return int(
            (self.remaining_sales_needed / Decimal(self.remaining_days)).quantize(
                Decimal("1"), rounding=ROUND_UP
            )
        )

    @property
    def status(self):
        if self.percent_time_elapsed == 0:
            return "⚪ Not Started"

        variance = self.projected_sales - self.target_amount

        if variance > 0:
            return "🟢 Ahead"

        if variance >= -(self.target_amount * Decimal("0.05")):
            return "🟡 On Track"

        return "🔴 Behind"


    @property
    def is_unit_campaign(self):
        return self.category.measurement_type == "units"

    @property
    def current_value(self):
        if self.is_unit_campaign:
            return self.current_units or Decimal("0")

        return self.current_sales or Decimal("0")

    @property
    def target_display(self):
        if self.is_unit_campaign:
            return f"{self.target_amount:,.0f}"

        return f"${self.target_amount:,.0f}"

    @property
    def current_display(self):
        if self.is_unit_campaign:
            return f"{self.current_value:,.0f}"

        return f"${self.current_value:,.0f}"

    @property
    def projected_display(self):
        if self.is_unit_campaign:
            return f"{self.projected_sales:,.0f}"

        return f"${self.projected_sales:,.0f}"

    @property
    def variance_display(self):
        if self.is_unit_campaign:
            return f"{self.projected_variance:,.0f}"

        return f"${self.projected_variance:,.0f}"

    @property
    def required_daily_display(self):
        if self.is_unit_campaign:
            return f"{self.required_daily_sales:,}"

        return f"${self.required_daily_sales:,}"

    @property
    def measurement_label(self):
        if self.is_unit_campaign:
            return "Units"

        return "Sales"

class SalesImportBatch(models.Model):
    STATUS_PREVIEW = "preview"
    STATUS_IMPORTED = "imported"
    STATUS_CANCELLED = "cancelled"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_PREVIEW, "Preview"),
        (STATUS_IMPORTED, "Imported"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_FAILED, "Failed"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    employer = models.ForeignKey(
        "user.employer",  # Change if needed
        on_delete=models.CASCADE,
        related_name="sales_import_batches",
    )
    target_period = models.ForeignKey(
        SalesTargetPeriod,
        on_delete=models.PROTECT,
        related_name="import_batches",
    )

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_import_batches",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PREVIEW,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    imported_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Sales import {self.id} - {self.status}"


class SalesImportFile(models.Model):
    batch = models.ForeignKey(
        SalesImportBatch,
        on_delete=models.CASCADE,
        related_name="files",
    )

    original_filename = models.CharField(max_length=255)

    store_number = models.CharField(
        max_length=50,
        blank=True,
    )

    from_date = models.DateField(
        null=True,
        blank=True,
    )

    to_date = models.DateField(
        null=True,
        blank=True,
    )

    is_valid = models.BooleanField(default=False)

    error_message = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = [
            "store_number",
            "original_filename",
        ]

    def __str__(self):
        if self.store_number:
            return f"{self.store_number} - {self.original_filename}"

        return self.original_filename


class SalesImportRow(models.Model):
    staged_file = models.ForeignKey(
        SalesImportFile,
        on_delete=models.CASCADE,
        related_name="rows",
    )

    target_category = models.ForeignKey(
        SalesTargetCategory,
        on_delete=models.PROTECT,
        related_name="staged_import_rows",
    )

    category_code = models.CharField(max_length=20)
    category_name = models.CharField(max_length=100)

    imported_sales = models.DecimalField(
        max_digits=14,
        decimal_places=2,
    )

    current_sales = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    difference = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    is_valid = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["category_name"]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "staged_file",
                    "target_category",
                ],
                name="unique_category_per_staged_sales_file",
            ),
        ]

    @property
    def is_skipped(self):
        return self.error_message.startswith("Skipped:")

    def __str__(self):
        return f"{self.staged_file.store_number} - {self.category_name}"
