import uuid
from datetime import timedelta
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

ROLES = [("auditor", "Auditor"), ("auditee", "Auditee"), ("committee", "Komite Unit"),
         ("redtag", "Red Tag Coordinator"), ("management", "Manajemen")]
PILLARS = [("ringkas", "Ringkas"), ("rapi", "Rapi"), ("resik", "Resik"), ("rawat", "Rawat"), ("rajin", "Rajin")]
STATUS = [("", "Menunggu penilaian"), ("DONE", "Done"), ("PROGRESS", "Progress"), ("NO_PROGRESS", "No Progress")]

def evidence_path(instance, filename):
    return f"photos/{uuid.uuid4().hex}.jpg"

class Unit(models.Model):
    name = models.CharField(max_length=120, unique=True)
    def __str__(self): return self.name

class Membership(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLES)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "unit", "role"], name="unique_membership")]

class Area(models.Model):
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT)
    name = models.CharField(max_length=120)
    location = models.CharField(max_length=120, blank=True)
    pics = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="pic_areas")
    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["unit", "name"], name="unique_area")]
    def __str__(self): return f"{self.name} · {self.location}"

class Question(models.Model):
    pillar = models.CharField(max_length=12, choices=PILLARS)
    text = models.CharField(max_length=240)
    active = models.BooleanField(default=True)
    def __str__(self): return self.text

class Audit(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    area = models.ForeignKey(Area, on_delete=models.PROTECT)
    period = models.DateField(help_text="Hari pertama bulan audit")
    auditor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    due_date = models.DateField()
    status = models.CharField(max_length=12, default="DRAFT", choices=[("DRAFT", "Draf"), ("SUBMITTED", "Terkirim")])
    board_photo = models.ImageField(upload_to=evidence_path, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        ordering = ["-period", "area__name"]
        constraints = [models.UniqueConstraint(fields=["area", "period"], name="unique_area_period")]
    def clean(self):
        if self.period and self.period.day != 1:
            raise ValidationError("Periode harus tanggal 1.")
        if self.area_id and self.auditor_id:
            if self.area.pics.filter(pk=self.auditor_id).exists():
                raise ValidationError("Auditor tidak boleh mengaudit area sendiri.")
            if not Membership.objects.filter(user_id=self.auditor_id, unit=self.area.unit, role="auditor").exists():
                raise ValidationError("Auditor harus terdaftar pada unit yang sama.")
    def __str__(self): return f"{self.area.name} / {self.period:%m-%Y}"

class Finding(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    audit = models.ForeignKey(Audit, on_delete=models.PROTECT, related_name="findings")
    question = models.ForeignKey(Question, on_delete=models.PROTECT)
    location = models.CharField(max_length=160)
    description = models.TextField(max_length=3000)
    photo = models.ImageField(upload_to=evidence_path)
    source = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="recurrences")
    priority = models.CharField(max_length=8, blank=True, choices=[("LOW", "Low"), ("HIGH", "High")])
    created_at = models.DateTimeField(default=timezone.now)
    class Meta:
        ordering = ["created_at"]
        constraints = [models.UniqueConstraint(fields=["audit", "source"], name="one_recurrence_per_source")]
    def __str__(self): return self.description[:80]

class Review(models.Model):
    audit = models.ForeignKey(Audit, on_delete=models.PROTECT, related_name="reviews")
    previous = models.ForeignKey(Finding, on_delete=models.PROTECT)
    required = models.BooleanField(default=False)
    verdict = models.CharField(max_length=12, blank=True, choices=[("EXISTS", "Masih ada"), ("HANDLED", "Sudah tidak ada")])
    photo = models.ImageField(upload_to=evidence_path, blank=True)
    note = models.TextField(max_length=3000, blank=True)
    version = models.PositiveIntegerField(default=0)
    checked_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        ordering = ["-required", "previous__created_at"]
        constraints = [models.UniqueConstraint(fields=["audit", "previous"], name="unique_previous_review")]

class FollowUp(models.Model):
    finding = models.OneToOneField(Finding, on_delete=models.PROTECT, related_name="followup")
    root_cause = models.TextField(max_length=3000, blank=True)
    corrective = models.TextField(max_length=3000, blank=True)
    preventive = models.TextField(max_length=3000, blank=True)
    work_order = models.CharField(max_length=120, blank=True)
    due_date = models.DateField(null=True, blank=True)
    photo = models.ImageField(upload_to=evidence_path, blank=True)
    status = models.CharField(max_length=12, choices=STATUS, blank=True)
    committee_note = models.TextField(max_length=3000, blank=True)
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="followups")
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="verifications")
    verified_at = models.DateTimeField(null=True, blank=True)

class RedTag(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    area = models.ForeignKey(Area, on_delete=models.PROTECT)
    finding = models.ForeignKey(Finding, null=True, blank=True, on_delete=models.PROTECT)
    name = models.CharField(max_length=160)
    reason = models.TextField(max_length=3000)
    location = models.CharField(max_length=160)
    photo = models.ImageField(upload_to=evidence_path)
    registered_on = models.DateField(default=timezone.localdate)
    due_date = models.DateField(editable=False)
    status = models.CharField(max_length=12, default="OPEN", choices=[("OPEN", "Aktif"), ("RETURNED", "Dikembalikan"), ("RELOCATED", "Dipindahkan"), ("DISPOSED", "Dibuang")])
    decision_note = models.TextField(max_length=3000, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="redtag_decisions")
    escalated_at = models.DateTimeField(null=True, blank=True)
    committee_note = models.TextField(max_length=3000, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    @property
    def tag_number(self): return f"RT-{self.registered_on.year}-{str(self.id)[:8].upper()}"
    @property
    def days_left(self): return (self.due_date - timezone.localdate()).days
    @property
    def overdue(self): return self.status == "OPEN" and self.days_left < 0
    def save(self, *args, **kwargs):
        self.due_date = self.registered_on + timedelta(days=90)
        return super().save(*args, **kwargs)

class Activity(models.Model):
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    text = models.CharField(max_length=500)
    created_at = models.DateTimeField(default=timezone.now)
    class Meta: ordering = ["-created_at"]

class SyncReceipt(models.Model):
    id = models.UUIDField(primary_key=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    audit = models.ForeignKey(Audit, on_delete=models.CASCADE)
    created_at = models.DateTimeField(default=timezone.now)
