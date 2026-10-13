import csv
import json
import uuid
from datetime import date
from pathlib import Path
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from .models import *
from .forms import FindingForm, ReviewForm, FollowUpForm, RedTagForm, ScheduleForm
from .permissions import *
from .services import *

def error_message(exc):
    return "; ".join(exc.messages) if isinstance(exc, ValidationError) else str(exc)

def forbidden(request): return render(request, "core/error.html", {"message": "Anda tidak memiliki akses untuk tindakan ini."}, status=403)

@require_POST
def demo_login(request):
    if not settings.DEMO_MODE: raise Http404
    role = request.POST.get("role", "")
    if role not in dict(ROLES): raise Http404
    user = get_object_or_404(get_user_model(), username=f"demo_{role}", is_active=True)
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return redirect("home")

@require_POST
def sign_out(request):
    logout(request)
    response = redirect("login")
    response["Clear-Site-Data"] = '"cache", "storage"'
    return response

@login_required
def home(request):
    audits = visible_audits(request.user).select_related("area", "auditor")
    findings = visible_findings(request.user).filter(audit__status="SUBMITTED")
    activities = Activity.objects.filter(unit_id__in=units_for(request.user))
    if not list(units_for(request.user, "committee")):
        activities = activities.filter(actor=request.user)
    return render(request, "core/home.html", {"audits": audits[:5], "finding_count": findings.count(),
        "pending_count": findings.filter(Q(followup__isnull=True) | Q(followup__status="")).count(),
        "audit_count": audits.filter(status="DRAFT").count(), "done_count": findings.filter(followup__status="DONE").count(),
        "activities": activities[:6]})

@login_required
def audits(request):
    qs = visible_audits(request.user).select_related("area__unit", "auditor")
    if request.GET.get("status") in {"DRAFT", "SUBMITTED"}: qs = qs.filter(status=request.GET["status"])
    rows = [{"audit": a, **audit_readiness(a)} for a in qs]
    return render(request, "core/audits.html", {"rows": rows})

@login_required
def audit_detail(request, pk):
    audit = get_object_or_404(visible_audits(request.user).select_related("area__unit", "auditor"), pk=pk)
    committee = has_role(request.user, audit.area.unit_id, "committee")
    if request.method == "POST":
        try:
            if request.POST.get("action") == "select":
                if not committee or audit.status != "DRAFT": return forbidden(request)
                with transaction.atomic():
                    Audit.objects.select_for_update().get(pk=audit.pk)
                    if Audit.objects.get(pk=audit.pk).status != "DRAFT": raise ValidationError("Audit sudah dikirim.")
                    ids = request.POST.getlist("required")
                    audit.reviews.update(required=False)
                    audit.reviews.filter(id__in=ids).update(required=True)
                    log(request.user, audit.area.unit_id, "Komite menetapkan pemeriksaan ulang wajib.")
                messages.success(request, "Pilihan pemeriksaan ulang disimpan.")
            elif request.POST.get("action") == "submit":
                submit_audit(request.user, audit)
                messages.success(request, "Audit dikirim ke Komite Unit.")
            else: raise ValidationError("Tindakan tidak valid.")
        except ValidationError as exc: messages.error(request, error_message(exc))
        return redirect("audit_detail", pk=pk)
    findings = audit.findings.select_related("question", "followup")
    q = request.GET.get("q", "").strip()
    if q: findings = findings.filter(Q(description__icontains=q) | Q(location__icontains=q))
    return render(request, "core/audit_detail.html", {"audit": audit, "findings": findings,
        "reviews": audit.reviews.select_related("previous__question", "previous__followup", "previous__audit"),
        "can_edit": can_edit_audit(request.user, audit), "committee": committee, **audit_readiness(audit)})

@login_required
def finding_add(request, pk):
    audit = get_object_or_404(visible_audits(request.user), pk=pk)
    if not can_edit_audit(request.user, audit): return forbidden(request)
    form = FindingForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            locked = Audit.objects.select_for_update().get(pk=pk)
            if locked.status != "DRAFT": return forbidden(request)
            finding = form.save(commit=False)
            finding.audit = audit
            finding.save()
            log(request.user, audit.area.unit_id, f"Temuan baru: {finding.description[:120]}")
        messages.success(request, "Temuan tersimpan.")
        return redirect("finding_add" if "another" in request.POST else "audit_detail", pk=pk)
    return render(request, "core/form.html", {"title": "Tambah Temuan", "subtitle": str(audit), "form": form,
        "back": f"/audit/{pk}/", "another": True, "photo_first": True})

@login_required
def finding_edit(request, pk):
    finding = get_object_or_404(visible_findings(request.user), pk=pk)
    if finding.source_id or not can_edit_audit(request.user, finding.audit): return forbidden(request)
    form = FindingForm(request.POST or None, request.FILES or None, instance=finding)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            audit = Audit.objects.select_for_update().get(pk=finding.audit_id)
            if not can_edit_audit(request.user, audit): return forbidden(request)
            form.save()
            log(request.user, audit.area.unit_id, f"Temuan diperbarui: {finding.description[:120]}")
        messages.success(request, "Perubahan temuan tersimpan.")
        return redirect("audit_detail", pk=finding.audit_id)
    return render(request, "core/form.html", {"title": "Edit Temuan", "subtitle": str(finding.audit),
        "form": form, "back": f"/audit/{finding.audit_id}/", "photo_first": True})

@login_required
def review_detail(request, pk):
    review = get_object_or_404(Review.objects.select_related("audit__area", "previous__question", "previous__audit"), pk=pk, audit__in=visible_audits(request.user))
    if not can_edit_audit(request.user, review.audit): return forbidden(request)
    form = ReviewForm(request.POST or None, request.FILES or None, initial={"version": review.version, "verdict": review.verdict, "note": review.note})
    if request.method == "POST" and form.is_valid():
        try:
            data = form.cleaned_data
            # ReviewForm already normalizes the uploaded image; the service validates again for API parity.
            review_previous(request.user, review, data["verdict"], data["note"], data["photo"], data["version"])
            messages.success(request, "Hasil pemeriksaan ulang tersimpan.")
            return redirect("audit_detail", pk=review.audit_id)
        except ValidationError as exc: form.add_error(None, error_message(exc))
    return render(request, "core/review.html", {"review": review, "form": form})

@login_required
def followups(request):
    qs = visible_findings(request.user).filter(audit__status="SUBMITTED")
    q, status, pillar = (request.GET.get(x, "") for x in ["q", "status", "pillar"])
    if q: qs = qs.filter(Q(description__icontains=q) | Q(audit__area__name__icontains=q))
    if status == "pending": qs = qs.filter(Q(followup__status="") | Q(followup__isnull=True))
    elif status in {"DONE", "PROGRESS", "NO_PROGRESS"}: qs = qs.filter(followup__status=status)
    if pillar in dict(PILLARS): qs = qs.filter(question__pillar=pillar)
    return render(request, "core/followups.html", {"findings": qs, "pillars": PILLARS})

@login_required
def finding_detail(request, pk):
    finding = get_object_or_404(visible_findings(request.user), pk=pk)
    unit_id = finding.audit.area.unit_id
    committee = has_role(request.user, unit_id, "committee")
    auditee = has_role(request.user, unit_id, "auditee") and finding.audit.area.pics.filter(pk=request.user.pk).exists()
    capa = FollowUp.objects.filter(finding=finding).first()
    can_fill = auditee and finding.priority and finding.audit.status == "SUBMITTED" and not (capa and capa.status)
    form = FollowUpForm(request.POST if request.method == "POST" and request.POST.get("action") == "capa" else None, request.FILES or None, instance=capa)
    if request.method == "POST":
        action = request.POST.get("action")
        try:
            with transaction.atomic():
                Finding.objects.select_for_update().get(pk=pk)
                if finding.audit.status != "SUBMITTED": raise ValidationError("Audit belum dikirim.")
                if action == "priority":
                    if not committee: return forbidden(request)
                    priority = request.POST.get("priority")
                    if priority not in {"LOW", "HIGH"}: raise ValidationError("Pilih prioritas.")
                    finding.priority = priority
                    finding.save(update_fields=["priority"])
                    log(request.user, unit_id, f"Prioritas {priority}: {finding.description[:100]}")
                elif action == "capa":
                    current = FollowUp.objects.filter(finding=finding).first()
                    if not can_fill or (current and current.status): return forbidden(request)
                    if not form.is_valid(): return render(request, "core/finding.html", {"finding": finding, "capa": capa, "committee": committee, "can_fill": can_fill, "form": form})
                    obj = form.save(commit=False)
                    obj.finding, obj.submitted_by = finding, request.user
                    obj.save()
                    log(request.user, unit_id, f"Tindak lanjut diajukan: {finding.description[:100]}")
                elif action == "verify":
                    if not committee: return forbidden(request)
                    if not finding.priority: raise ValidationError("Tetapkan prioritas terlebih dahulu.")
                    obj, _ = FollowUp.objects.get_or_create(finding=finding)
                    status = request.POST.get("status", "")
                    if status not in {"DONE", "PROGRESS", "NO_PROGRESS"}: raise ValidationError("Pilih hasil penilaian.")
                    if status == "PROGRESS" and not obj.work_order.strip(): raise ValidationError("Progress memerlukan nomor WO / SC / PO dari Auditee.")
                    if status == "DONE" and not (obj.corrective.strip() and obj.photo): raise ValidationError("Done memerlukan tindakan koreksi dan foto perbaikan.")
                    if request.POST.get("note", "").strip() == "": raise ValidationError("Catatan penilaian wajib diisi.")
                    obj.status, obj.committee_note = status, request.POST["note"][:3000]
                    obj.verified_by, obj.verified_at = request.user, timezone.now()
                    obj.save()
                    log(request.user, unit_id, f"Komite menilai {status}: {finding.description[:100]}")
                else: raise ValidationError("Tindakan tidak valid.")
            messages.success(request, "Perubahan tersimpan.")
        except ValidationError as exc: messages.error(request, error_message(exc))
        return redirect("finding_detail", pk=pk)
    return render(request, "core/finding.html", {"finding": finding, "capa": capa, "committee": committee, "can_fill": can_fill, "form": form,
        "linked_tags": visible_tags(request.user).filter(finding=finding), "can_register": auditee})

@login_required
def redtags(request):
    qs = visible_tags(request.user).select_related("area")
    if request.GET.get("status") == "overdue": qs = qs.filter(status="OPEN", due_date__lt=timezone.localdate())
    elif request.GET.get("status") == "OPEN": qs = qs.filter(status="OPEN")
    q = request.GET.get("q", "")
    if q: qs = qs.filter(Q(name__icontains=q) | Q(location__icontains=q))
    return render(request, "core/redtags.html", {"tags": qs.order_by("due_date"), "can_create": bool(list(units_for(request.user, "redtag", "auditee")))})

@login_required
def redtag_add(request):
    form = RedTagForm(request.POST or None, request.FILES or None, user=request.user)
    source = None
    if request.GET.get("finding"):
        source = get_object_or_404(visible_findings(request.user), pk=request.GET["finding"])
        form.initial["area"] = source.audit.area
    if request.method == "POST" and form.is_valid():
        tag = form.save(commit=False)
        if source and tag.area_id != source.audit.area_id:
            form.add_error("area", "Area harus sama dengan temuan asal.")
        else:
            tag.finding, tag.created_by = source, request.user
            tag.save()
            log(request.user, tag.area.unit_id, f"Red tag {tag.tag_number} didaftarkan; tenggat {tag.due_date}.")
            return redirect("redtag_detail", pk=tag.pk)
    return render(request, "core/form.html", {"title": "Daftarkan Red Tag", "subtitle": "90 hari sejak pemasangan · eskalasi ke Komite Unit", "form": form, "back": "/redtag/"})

@login_required
def redtag_detail(request, pk):
    tag = get_object_or_404(visible_tags(request.user).select_related("area__unit"), pk=pk)
    coordinator = has_role(request.user, tag.area.unit_id, "redtag")
    committee = has_role(request.user, tag.area.unit_id, "committee")
    if request.method == "POST":
        with transaction.atomic():
            tag = RedTag.objects.select_for_update().get(pk=pk)
            note = request.POST.get("note", "").strip()[:3000]
            if not note: messages.error(request, "Catatan wajib diisi.")
            elif request.POST.get("action") == "decision" and coordinator and tag.status == "OPEN":
                status = request.POST.get("status")
                if status not in {"RETURNED", "RELOCATED", "DISPOSED"}: return forbidden(request)
                tag.status, tag.decision_note = status, note
                tag.decided_by, tag.decided_at = request.user, timezone.now()
                tag.save()
                log(request.user, tag.area.unit_id, f"Red tag {tag.tag_number}: {tag.get_status_display()}")
            elif request.POST.get("action") == "escalation" and committee and tag.overdue:
                tag.committee_note = note
                tag.escalated_at = tag.escalated_at or timezone.now()
                tag.save()
                log(request.user, tag.area.unit_id, f"Komite menindaklanjuti eskalasi {tag.tag_number}.")
            else: return forbidden(request)
        return redirect("redtag_detail", pk=pk)
    return render(request, "core/redtag.html", {"tag": tag, "coordinator": coordinator, "committee": committee})

@login_required
def schedule(request):
    form = ScheduleForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            audit = form.save()
            prepare_reviews(audit)
            log(request.user, audit.area.unit_id, f"Penugasan audit {audit.area.name} dibuat.")
        messages.success(request, "Penugasan dibuat. Pilih temuan pemeriksaan ulang di ruang audit.")
        return redirect("audit_detail", pk=audit.pk)
    return render(request, "core/schedule.html", {"form": form, "audits": visible_audits(request.user).select_related("area", "auditor")})

@login_required
def reports(request):
    if not list(units_for(request.user, "committee", "management", "auditor")): return forbidden(request)
    period = request.GET.get("period", timezone.localdate().strftime("%Y-%m"))
    try: selected = date.fromisoformat(period + "-01")
    except ValueError: selected = timezone.localdate().replace(day=1)
    rows = []
    for audit in visible_audits(request.user).filter(period=selected, status="SUBMITTED").select_related("area"):
        rows.append({"area": audit.area.name, **score_summary(audit.findings.select_related("followup"))})
    if request.GET.get("export") == "csv":
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="5r-{selected:%Y-%m}.csv"'
        response.write("\ufeff")
        writer = csv.writer(response)
        writer.writerow(["Area", "Done", "Progress", "No Progress", "Belum dinilai", "Nilai utama sementara", "Berulang", "Parking Lot"])
        for row in rows:
            values = [row[k] for k in ["area", "done", "progress", "no_progress", "pending", "main", "recurring", "parking"]]
            writer.writerow([("'" + v) if isinstance(v, str) and v.startswith(("=", "+", "-", "@", "\t", "\r")) else v for v in values])
        return response
    return render(request, "core/reports.html", {"rows": rows, "period": selected.strftime("%Y-%m")})

@login_required
@never_cache
def evidence(request, kind, pk):
    if kind == "finding":
        # Assigned auditors must see evidence from last month's audit even when another auditor performed it.
        previous_ids = Review.objects.filter(audit__in=visible_audits(request.user)).values_list("previous_id", flat=True)
        allowed = Finding.objects.filter(Q(pk__in=visible_findings(request.user).values("pk")) | Q(pk__in=previous_ids))
        obj = get_object_or_404(allowed, pk=pk)
        photo = obj.photo
    elif kind == "after": obj = get_object_or_404(visible_findings(request.user), pk=pk); photo = getattr(getattr(obj, "followup", None), "photo", None)
    elif kind == "review": obj = get_object_or_404(Review, pk=pk, audit__in=visible_audits(request.user)); photo = obj.photo
    elif kind == "redtag": obj = get_object_or_404(visible_tags(request.user), pk=pk); photo = obj.photo
    else: raise Http404
    if not photo: raise Http404
    try: response = FileResponse(photo.open("rb"), content_type="image/jpeg")
    except FileNotFoundError: raise Http404
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response

def offline(request): return render(request, "core/offline.html")

def service_worker(request):
    response = HttpResponse((settings.BASE_DIR / "static" / "sw.js").read_text(encoding="utf-8"), content_type="application/javascript")
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache"
    return response

@never_cache
def session_info(request):
    if not request.user.is_authenticated: return JsonResponse({"error": "Login kembali untuk sinkronisasi."}, status=401)
    return JsonResponse({"user": request.user.pk, "csrf": get_token(request)})

@never_cache
def audit_snapshot(request, pk):
    if not request.user.is_authenticated: return JsonResponse({"error": "Login diperlukan."}, status=401)
    audit = get_object_or_404(visible_audits(request.user), pk=pk)
    if not can_edit_audit(request.user, audit): return JsonResponse({"error": "Audit tidak dapat dikerjakan offline."}, status=403)
    reviews = [{"id": r.pk, "version": r.version, "required": r.required, "verdict": r.verdict,
        "description": r.previous.description, "location": r.previous.location,
        "photo": f"/evidence/finding/{r.previous_id}/"} for r in audit.reviews.select_related("previous")]
    return JsonResponse({"user": request.user.pk, "id": str(audit.pk), "area": audit.area.name,
        "period": str(audit.period), "reviews": reviews, "new_count": audit_readiness(audit)["new_count"],
        "questions": list(Question.objects.filter(active=True).values("id", "pillar", "text")), "saved_at": timezone.now().isoformat()})

@require_POST
@never_cache
def sync_operation(request, pk):
    if not request.user.is_authenticated: return JsonResponse({"error": "Login kembali sebelum sinkronisasi."}, status=401)
    try:
        op_id = uuid.UUID(request.POST.get("operation", ""))
        if str(request.user.pk) != request.POST.get("user"): return JsonResponse({"error": "Draf milik akun berbeda. Login dengan akun pembuat."}, status=403)
        with transaction.atomic():
            audit = get_object_or_404(Audit.objects.select_for_update(), pk=pk)
            receipt = SyncReceipt.objects.filter(pk=op_id).first()
            if receipt:
                if receipt.user_id != request.user.id or receipt.audit_id != audit.pk: return JsonResponse({"error": "Identitas operasi tidak cocok."}, status=409)
                return JsonResponse({"ok": True, "duplicate": True})
            if not can_edit_audit(request.user, audit): return JsonResponse({"error": "Audit sudah dikirim atau penugasan berubah. Draf tetap disimpan."}, status=409)
            if request.POST.get("kind") == "finding":
                form = FindingForm(request.POST, request.FILES)
                if not form.is_valid(): return JsonResponse({"error": form.errors.get_json_data()}, status=422)
                if Finding.objects.filter(pk=op_id).exists(): return JsonResponse({"error": "ID temuan sudah digunakan."}, status=409)
                finding = form.save(commit=False)
                finding.id, finding.audit = op_id, audit
                finding.save()
                log(request.user, audit.area.unit_id, "Temuan offline disinkronkan.")
            elif request.POST.get("kind") == "review":
                review = get_object_or_404(Review, pk=request.POST.get("review"), audit=audit)
                review_previous(request.user, review, request.POST.get("verdict"), request.POST.get("note", "")[:3000], request.FILES.get("photo"), int(request.POST.get("version", "-1")))
            else: raise ValidationError("Jenis operasi tidak valid.")
            SyncReceipt.objects.create(id=op_id, user=request.user, audit=audit)
        return JsonResponse({"ok": True})
    except (ValueError, ValidationError) as exc: return JsonResponse({"error": error_message(exc)}, status=409)
