from django.contrib import admin

from .models import Household


@admin.register(Household)
class HouseholdAdmin(admin.ModelAdmin):
    list_display = ["name", "branch", "head"]
    search_fields = ["name"]
