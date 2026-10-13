from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageOps, UnidentifiedImageError
from .models import Audit, Review, Finding, Activity, RedTag

def clean_photo(upload):
    if not upload: raise ValidationError("Foto bukti wajib diisi.")
    if upload.size > 10 * 1024 * 1024: raise ValidationError("Ukuran foto maksimal 10 MB.")
    try:
        image = Image.open(upload)
        if image.width * image.height > 25000000: raise ValidationError("Resolusi foto terlalu besar.")
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((1600, 1600))
        output = BytesIO()
        image.save(output, format="JPEG", quality=85)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValidationError("Unggah foto JPG, PNG, atau WebP yang valid.") from exc
    return ContentFile(output.getvalue(), name="photo.jpg")

def log(user, unit_id, text):
    Activity.objects.create(actor=user, unit_id=unit_id, text=text)

def prepare_reviews(audit):
    previous_period = (audit.period - timedelta(days=1)).replace(day=1)
    previous = Finding.objects.filter(audit__area=audit.area, audit__period=previous_period, audit__status="SUBMITTED")
    for finding in previous:
        Review.objects.get_or_create(audit=audit, previous=finding)

@transaction.atomic
def review_previous(user, review, verdict, note, photo, expected_version):
    audit = Audit.objects.select_for_update().get(pk=review.audit_id)
    review = Review.objects.select_for_update().select_related("previous").get(pk=review.pk)
    from .permissions import can_edit_audit
    if not can_edit_audit(user, audit): raise ValidationError("Audit tidak dapat diubah.")
    if review.version != expected_version: raise ValidationError("Pemeriksaan sudah berubah. Muat ulang sebelum menyimpan.")
    if verdict not in {"EXISTS", "HANDLED"}: raise ValidationError("Pilih hasil pemeriksaan.")
    review.verdict, review.note, review.photo = verdict, note, clean_photo(photo)
    review.version += 1
    review.checked_at = timezone.now()
    review.save()
    if verdict == "EXISTS":
        Finding.objects.update_or_create(audit=audit, source=review.previous, defaults={
            "question": review.previous.question, "location": review.previous.location,
            "description": review.previous.description, "photo": review.photo.name,
        })
    else:
        Finding.objects.filter(audit=audit, source=review.previous).delete()
    log(user, audit.area.unit_id, f"Pemeriksaan ulang: {review.get_verdict_display()} — {review.previous.description[:100]}")
    return review

def audit_readiness(audit):
    count = audit.findings.filter(source__isnull=True).count()
    required = audit.reviews.filter(required=True)
    remaining = required.filter(verdict="").count()
    return {"new_count": count, "required_count": required.count(), "remaining": remaining,
            "checked_count": audit.reviews.exclude(verdict="").count(),
            "all_count": audit.reviews.count(), "ready": count >= 20 and remaining == 0}

@transaction.atomic
def submit_audit(user, audit):
    audit = Audit.objects.select_for_update().get(pk=audit.pk)
    from .permissions import can_edit_audit
    if not can_edit_audit(user, audit): raise ValidationError("Audit tidak dapat dikirim.")
    if not audit_readiness(audit)["ready"]:
        raise ValidationError("Lengkapi 20 temuan baru dan pemeriksaan ulang wajib dari Komite Unit.")
    audit.status = "SUBMITTED"
    audit.submitted_at = timezone.now()
    audit.save(update_fields=["status", "submitted_at"])
    log(user, audit.area.unit_id, f"Audit {audit.area.name} periode {audit.period:%m/%Y} dikirim.")

def score_summary(findings):
    findings = list(findings)
    statuses = [getattr(getattr(f, "followup", None), "status", "") for f in findings]
    done, progress, no_progress = (statuses.count(s) for s in ["DONE", "PROGRESS", "NO_PROGRESS"])
    evaluated = done + progress + no_progress
    main = None
    if evaluated:
        main = (Decimal(2 * done + progress - no_progress) / (2 * evaluated) * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    recurring = sum(f.source_id is not None for f in findings)
    # Parking-lot penalty is an unresolved business decision. Never label this a final score.
    return {"done": done, "progress": progress, "no_progress": no_progress, "pending": len(findings)-evaluated,
            "main": main, "recurring": recurring, "parking": progress+no_progress, "total": len(findings)}

@transaction.atomic
def escalate_overdue():
    tags = RedTag.objects.select_for_update().filter(status="OPEN", due_date__lt=timezone.localdate(), escalated_at__isnull=True)
    count = 0
    for tag in tags:
        tag.escalated_at = timezone.now()
        tag.save(update_fields=["escalated_at"])
        Activity.objects.create(unit=tag.area.unit, text=f"Red tag {tag.tag_number} melewati 90 hari; eskalasi ke Komite Unit.")
        count += 1
    return count
