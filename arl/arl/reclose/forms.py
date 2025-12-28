from django import forms
from .models import RecClose


class RecCloseForm(forms.ModelForm):
    class Meta:
        model = RecClose
        fields = [
            "store_number",
            "shift_number",
            "total_sales",
            "cat_post_host",
            "drive_offs",
            "purchases",
            "ppts_redemptions",
            "lotto_payout",
            "uber_eats",
            "skip",
            "drive_off_recovery",
            "cash_safe_drops",
            "last_safe_drop",
            "in_brink",
            # Tanks
            "tank1_name",
            "tank1_tc_volume",
            "tank1_height",
            "tank1_water",
            "tank1_water_height",
            "tank1_temperature",
            "tank2_name",
            "tank2_tc_volume",
            "tank2_height",
            "tank2_water",
            "tank2_water_height",
            "tank2_temperature",
            "tank3_name",
            "tank3_tc_volume",
            "tank3_height",
            "tank3_water",
            "tank3_water_height",
            "tank3_temperature",
            "tank4_name",
            "tank4_tc_volume",
            "tank4_height",
            "tank4_water",
            "tank4_water_height",
            "tank4_temperature",
            # Inventory
            "pump_total_inventory",
            # Meter Discrepancy
            "meter1_sales",
            "meter1_meter",
            "meter1_difference",
            "meter2_sales",
            "meter2_meter",
            "meter2_difference",
            "meter3_sales",
            "meter3_meter",
            "meter3_difference",
            "meter4_sales",
            "meter4_meter",
            "meter4_difference",
        ]
        widgets = {
            field: forms.NumberInput(attrs={"class": "form-control", "step": "0.01"})
            for field in fields
        }

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

            # Group tank fields
            self.tank_fields = []
            for i in range(1, 5):
                tank_data = []
                for suffix in [
                    "name",
                    "tc_volume",
                    "height",
                    "water",
                    "water_height",
                    "temperature",
                ]:
                    field_name = f"tank{i}_{suffix}"
                    if field_name in self.fields:
                        tank_data.append((field_name, self[field_name]))
                self.tank_fields.append(tank_data)

            # Group meter discrepancy fields
            self.meter_fields = []
            for i in range(1, 5):
                meter_data = []
                for suffix in ["sales", "meter", "difference"]:
                    field_name = f"meter{i}_{suffix}"
                    if field_name in self.fields:
                        meter_data.append((field_name, self[field_name]))
                self.meter_fields.append(meter_data)
