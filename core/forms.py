from django import forms
from django.contrib.auth import get_user_model
from .models import Finding, Question, FollowUp, RedTag, Audit, Membership
from .permissions import visible_areas, units_for
from .services import clean_photo

class PhotoFormMixin:
    def clean_photo(self):
        photo = self.cleaned_data.get("photo")
        if photo and hasattr(photo, "content_type"): return clean_photo(photo)
        return photo

class FindingForm(PhotoFormMixin, forms.ModelForm):
    class Meta:
        model = Finding
        fields = ["photo", "question", "location", "description"]
        labels = {"photo": "Foto temuan", "question": "Pertanyaan panduan / kategori 5R", "location": "Lokasi detail", "description": "Deskripsi temuan"}
        widgets = {"description": forms.Textarea(attrs={"rows": 4, "placeholder": "Jelaskan kondisi yang ditemukan…"}),
                   "photo": forms.FileInput(attrs={"accept": "image/jpeg,image/png,image/webp"})}
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["question"].queryset = Question.objects.filter(active=True).order_by("pillar", "id")
        self.fields["question"].label_from_instance = lambda q: f"{q.get_pillar_display()} — {q.text}"

class ReviewForm(PhotoFormMixin, forms.Form):
    verdict = forms.ChoiceField(label="Bagaimana kondisi saat ini?", choices=[("EXISTS", "Masih ada"), ("HANDLED", "Sudah tidak ada")], widget=forms.RadioSelect)
    photo = forms.ImageField(label="Foto kondisi terbaru", widget=forms.FileInput(attrs={"accept": "image/*"}))
    note = forms.CharField(label="Catatan pemeriksaan", max_length=3000, required=False, widget=forms.Textarea(attrs={"rows": 3}))
    version = forms.IntegerField(widget=forms.HiddenInput)

class FollowUpForm(PhotoFormMixin, forms.ModelForm):
    class Meta:
        model = FollowUp
        fields = ["root_cause", "corrective", "preventive", "work_order", "due_date", "photo"]
        labels = {"root_cause": "Akar masalah", "corrective": "Tindakan koreksi", "preventive": "Tindakan pencegahan", "work_order": "Nomor WO / SC / PO", "due_date": "Target selesai", "photo": "Foto setelah perbaikan"}
        widgets = {f: forms.Textarea(attrs={"rows": 3}) for f in ["root_cause", "corrective", "preventive"]} | {"due_date": forms.DateInput(attrs={"type": "date"}), "photo": forms.FileInput(attrs={"accept": "image/*"})}
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in ["root_cause", "corrective", "preventive"]: self.fields[field].required = True
        self.fields["work_order"].help_text = "Wajib tersedia jika Komite menilai Progress."

class RedTagForm(PhotoFormMixin, forms.ModelForm):
    class Meta:
        model = RedTag
        fields = ["area", "name", "reason", "location", "registered_on", "photo"]
        labels = {"area": "Area", "name": "Nama barang", "reason": "Alasan red tag", "location": "Lokasi barang", "registered_on": "Tanggal pemasangan", "photo": "Foto barang"}
        widgets = {"reason": forms.Textarea(attrs={"rows": 3}), "registered_on": forms.DateInput(attrs={"type": "date"}), "photo": forms.FileInput(attrs={"accept": "image/*"})}
    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        from django.db.models import Q
        self.fields["area"].queryset = visible_areas(user).filter(Q(unit_id__in=units_for(user, "redtag")) | Q(pics=user, unit_id__in=units_for(user, "auditee"))).distinct()
    def clean_registered_on(self):
        from django.utils import timezone
        date = self.cleaned_data["registered_on"]
        if date > timezone.localdate(): raise forms.ValidationError("Tanggal pemasangan tidak boleh di masa depan.")
        return date

class ScheduleForm(forms.ModelForm):
    class Meta:
        model = Audit
        fields = ["area", "period", "auditor", "due_date"]
        labels = {"area": "Area", "period": "Periode (tanggal 1)", "auditor": "Auditor", "due_date": "Batas audit"}
        widgets = {"period": forms.DateInput(attrs={"type": "date"}), "due_date": forms.DateInput(attrs={"type": "date"})}
    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        units = units_for(user, "committee")
        self.fields["area"].queryset = visible_areas(user).filter(unit_id__in=units)
        self.fields["auditor"].queryset = get_user_model().objects.filter(is_active=True, membership__role="auditor", membership__unit_id__in=units).distinct()
