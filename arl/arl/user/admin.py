from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Employer


fields = list(UserAdmin.fieldsets)
fields[1] = ('Personal Info', {'fields': ('employer','first_name', 'last_name', 'email',
                 'phone_number', 'mon_avail', 'tue_avail', 'wed_avail', 'thu_avail',
                   'fri_avail', 'sat_avail', 'sun_avail')})


UserAdmin.fieldsets = tuple(fields)


admin.site.register(CustomUser, UserAdmin)
admin.site.register(Employer)

