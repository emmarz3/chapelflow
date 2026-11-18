from django.contrib import admin

from .models import FinancialStatement, Giving, GivingCategory, Payment, Pledge, Reconciliation, Refund

admin.site.register(GivingCategory)


@admin.register(Giving)
class GivingAdmin(admin.ModelAdmin):
    list_display = ["id", "branch", "member", "category", "amount", "currency", "status", "source", "given_at"]
    list_filter = ["status", "source", "branch", "category"]
    readonly_fields = ["id", "status", "recorded_by", "created_at"]
    search_fields = ["member__first_name", "member__last_name", "note"]


admin.site.register(Pledge)
admin.site.register(FinancialStatement)
admin.site.register(Reconciliation)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["provider", "provider_reference", "amount", "status", "created_at"]
    list_filter = ["provider", "status"]
    readonly_fields = ["raw_webhook_payload", "status", "confirmed_at"]


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ["id", "original_giving", "amount", "refunded_by", "refunded_at"]
    list_filter = ["refunded_at"]
    readonly_fields = ["id", "refunded_by", "refunded_at"]
    search_fields = ["original_giving__id", "reason"]
