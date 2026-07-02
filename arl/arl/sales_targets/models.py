from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal


class SalesTargetCategory(models.Model):
    employer = models.ForeignKey(
        "user.Employer",
        on_delete=models.CASCADE,
        related_name="sales_target_categories",
    )
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("employer", "name")
        ordering = ["employer", "name"]
        verbose_name = "Sales Target Category"
        verbose_name_plural = "Sales Target Categories"

    def __str__(self):
        return f"{self.employer} - {self.name}"


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

    current_sales = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    last_updated = models.DateField(
        null=True,
        blank=True
    )
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

        return self.current_sales / self.target_amount * Decimal("100")


    @property
    def projected_sales(self):
        if self.elapsed_days == 0:
            return Decimal("0")

        daily_average = self.current_sales / Decimal(self.elapsed_days)
        return daily_average * Decimal(self.total_days)


    @property
    def projected_variance(self):
        return self.projected_sales - self.target_amount


    @property
    def remaining_sales_needed(self):
        return max(self.target_amount - self.current_sales, Decimal("0"))


    @property
    def required_daily_sales(self):
        if self.remaining_days == 0:
            return Decimal("0")

        return self.remaining_sales_needed / Decimal(self.remaining_days)

    @property
    def status(self):
        """
        Compare % of target achieved to % of time elapsed.
        """

        if self.percent_time_elapsed == 0:
            return "⚪ Not Started"

        performance = float(self.percent_to_target)
        expected = float(self.percent_time_elapsed)

        difference = performance - expected

        if difference >= 5:
            return "🟢 Ahead"

        if difference >= -5:
            return "🟡 On Track"

        return "🔴 Behind"