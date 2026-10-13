from django.contrib import admin
from django.contrib.auth.views import LoginView
from django.urls import path
from core import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("demo-login/", views.demo_login, name="demo_login"),
    path("logout/", views.sign_out, name="logout"),
    path("", views.home, name="home"),
    path("audit/", views.audits, name="audits"),
    path("audit/<uuid:pk>/", views.audit_detail, name="audit_detail"),
    path("audit/<uuid:pk>/temuan/", views.finding_add, name="finding_add"),
    path("review/<int:pk>/", views.review_detail, name="review_detail"),
    path("tindak-lanjut/", views.followups, name="followups"),
    path("temuan/<uuid:pk>/", views.finding_detail, name="finding_detail"),
    path("temuan/<uuid:pk>/edit/", views.finding_edit, name="finding_edit"),
    path("redtag/", views.redtags, name="redtags"),
    path("redtag/baru/", views.redtag_add, name="redtag_add"),
    path("redtag/<uuid:pk>/", views.redtag_detail, name="redtag_detail"),
    path("jadwal/", views.schedule, name="schedule"),
    path("laporan/", views.reports, name="reports"),
    path("evidence/<str:kind>/<str:pk>/", views.evidence, name="evidence"),
    path("offline/", views.offline, name="offline"),
    path("sw.js", views.service_worker),
    path("api/session/", views.session_info),
    path("api/audit/<uuid:pk>/", views.audit_snapshot),
    path("api/audit/<uuid:pk>/sync/", views.sync_operation),
]
