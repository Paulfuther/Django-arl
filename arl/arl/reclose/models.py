from django.db import models
from django.utils.timezone import now
from arl.user.models import Employer


class RecClose(models.Model):
    store_number = models.CharField(max_length=20)
    shift_number = models.PositiveIntegerField()
    timestamp = models.DateTimeField(default=now)
    user_employer = models.ForeignKey(
        Employer, on_delete=models.SET_NULL, null=True
    )

    # SECTION 1
    total_sales = models.DecimalField(max_digits=10, decimal_places=2)

    # SECTION 2 (manual entry for all fields)
    cat_post_host = models.PositiveIntegerField(default=0)
    drive_offs = models.PositiveIntegerField(default=0)
    purchases = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    ppts_redemptions = models.DecimalField("PPTS Redemptions ($1)", max_digits=10, decimal_places=2, default=0)
    lotto_payout = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    uber_eats = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    skip = models.DecimalField("SkipTheDishes", max_digits=10, decimal_places=2, default=0)
    drive_off_recovery = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cash_safe_drops = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    last_safe_drop = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    in_brink = models.DecimalField("In Brink", max_digits=10, decimal_places=2, default=0)

    # Tank readings (4 tanks)
    tank1_name = models.CharField(max_length=50, blank=True)
    tank1_tc_volume = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    tank1_height = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    tank1_water = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    tank1_water_height = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    tank1_temperature = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    tank2_name = models.CharField(max_length=50, blank=True)
    tank2_tc_volume = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    tank2_height = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    tank2_water = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    tank2_water_height = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    tank2_temperature = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    tank3_name = models.CharField(max_length=50, blank=True)
    tank3_tc_volume = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    tank3_height = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    tank3_water = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    tank3_water_height = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    tank3_temperature = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    tank4_name = models.CharField(max_length=50, blank=True)
    tank4_tc_volume = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    tank4_height = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    tank4_water = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    tank4_water_height = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    tank4_temperature = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    # Pump read
    pump_total_inventory = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    # Meter discrepancies (4 meters)
    meter1_sales = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    meter1_meter = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    meter1_difference = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    meter2_sales = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    meter2_meter = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    meter2_difference = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    meter3_sales = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    meter3_meter = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    meter3_difference = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    meter4_sales = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    meter4_meter = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    meter4_difference = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    @property
    def total_section_2(self):
        return (
            self.cat_post_host +
            self.drive_offs +
            self.purchases +
            self.ppts_redemptions +
            self.lotto_payout +
            self.uber_eats +
            self.skip +
            self.drive_off_recovery +
            self.cash_safe_drops +
            self.last_safe_drop +
            self.in_brink
        )

    @property
    def over_or_short(self):
        return self.total_section_2 - self.total_sales

    def __str__(self):
        return f"Shift {self.shift_number}"