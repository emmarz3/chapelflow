from django.contrib import admin

from .models import College, Department, University


@admin.register(University)
class UniversityAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "is_active")
    search_fields = ("name",)


@admin.register(College)
class CollegeAdmin(admin.ModelAdmin):
    list_display = ("name", "university", "is_active")
    search_fields = ("name",)
    list_filter = ("university",)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "college", "is_active")
    search_fields = ("name",)
    list_filter = ("college",)
