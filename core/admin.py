from django.contrib import admin
from .models import Unit, Area, Membership, Question, Audit, Activity

admin.site.site_header = "5R · Administrasi teknis"
for model in [Unit, Area, Membership, Question]: admin.site.register(model)

@admin.register(Audit)
class AuditAdmin(admin.ModelAdmin):
    list_display = ["area", "period", "auditor", "status"]
    def save_model(self, request, obj, form, change):
        from .services import prepare_reviews
        super().save_model(request, obj, form, change)
        prepare_reviews(obj)

@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ["created_at", "unit", "actor", "text"]
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
