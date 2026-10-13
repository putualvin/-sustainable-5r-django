from datetime import timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from core.models import *
from core.services import clean_photo, prepare_reviews, escalate_overdue

EXAMPLES = [
    ("ringkas", "Apakah ada barang yang tidak diperlukan?", "Suku cadang bekas menumpuk di area kerja", "Dekat pompa transfer", "cluttered-spare-parts.webp"),
    ("rapi", "Apakah barang disimpan di lokasi yang ditetapkan?", "Peralatan belum dikembalikan ke tempat penyimpanan", "Area maintenance", "cluttered-spare-parts.webp"),
    ("resik", "Apakah lantai dan peralatan dalam kondisi bersih?", "Tumpahan minyak di area pompa", "Pompa transfer", "lubricant-spill.webp"),
    ("rawat", "Apakah standar visual terawat dan terbaca?", "Marka jalur pejalan kaki mulai pudar", "Jalur utama", "faded-floor-marking.webp"),
    ("rajin", "Apakah standar penataan dipatuhi secara konsisten?", "Material kembali diletakkan di jalur akses", "Pintu masuk", "cluttered-spare-parts.webp"),
]

class Command(BaseCommand):
    help = "Membuat data demonstrasi fiktif. Idempoten; tidak menghapus atau mereset data."
    def handle(self, *args, **options):
        if not settings.DEMO_MODE: raise CommandError("Seed demo hanya boleh berjalan saat DEBUG=true dan DEMO_MODE=true.")
        unit, _ = Unit.objects.get_or_create(name="Unit Demonstrasi")
        if Audit.objects.filter(area__unit=unit).exists():
            self.stdout.write("Data demo sudah ada; tidak ditimpa.")
            return
        with transaction.atomic():
            users = {}
            for role, label in ROLES:
                user, created = get_user_model().objects.get_or_create(username=f"demo_{role}", defaults={"first_name": {"auditor":"Ardi", "auditee":"Dina", "committee":"Nadia", "redtag":"Raka", "management":"Bima"}[role]})
                if created: user.set_unusable_password(); user.save()
                Membership.objects.get_or_create(user=user, unit=unit, role=role)
                users[role] = user
            areas = []
            for name, location in [("Refinery", "Lantai 1"), ("Fractionation", "Lantai 1"), ("Workshop", "Area maintenance")]:
                area, _ = Area.objects.get_or_create(unit=unit, name=name, defaults={"location":location})
                area.pics.add(users["auditee"])
                areas.append(area)
            questions = [Question.objects.get_or_create(pillar=p, text=q)[0] for p,q,*_ in EXAMPLES]
            month = timezone.localdate().replace(day=1)
            last = (month-timedelta(days=1)).replace(day=1)
            def photo(name):
                return clean_photo(ContentFile((settings.BASE_DIR / "static" / "demo" / name).read_bytes(), name=name))
            def add(audit, index):
                _,_,description,location,filename = EXAMPLES[index % 5]
                return Finding.objects.create(audit=audit, question=questions[index%5], location=f"{location} · Zona {index//5+1}", description=description, photo=photo(filename), priority="HIGH" if index%3==0 else "LOW")
            previous = Audit.objects.create(area=areas[0], period=last, due_date=last.replace(day=10), auditor=users["auditor"], status="SUBMITTED", submitted_at=timezone.now()-timedelta(days=30))
            for index in range(20):
                finding = add(previous,index)
                FollowUp.objects.create(finding=finding, root_cause="Penyimpanan belum memiliki penanda yang konsisten.", corrective="Penataan ulang area dan peralatan.", preventive="Tetapkan penanggung jawab dan standar lokasi.", work_order="WO-DEMO-014", photo=photo(EXAMPLES[index%5][4]), status=["DONE","PROGRESS","NO_PROGRESS"][index%3], submitted_by=users["auditee"], verified_by=users["committee"], verified_at=timezone.now()-timedelta(days=26), committee_note="Contoh penilaian demonstrasi; foto ilustrasi.")
            current = Audit.objects.create(area=areas[0], period=month, auditor=users["auditor"], due_date=month.replace(day=10))
            prepare_reviews(current)
            for review in current.reviews.all()[:3]: review.required=True;review.save()
            for index in range(12):
                finding=add(current,index);finding.priority="";finding.save(update_fields=["priority"])
            submitted = Audit.objects.create(area=areas[1], period=month, auditor=users["auditor"], due_date=month.replace(day=10), status="SUBMITTED", submitted_at=timezone.now())
            for index in range(20):
                finding=add(submitted,index)
                if index%4==0: continue
                FollowUp.objects.create(finding=finding, root_cause="Belum ada standar visual penataan.", corrective="Area dirapikan dan material dipisahkan.", preventive="Terapkan label lokasi dan penanggung jawab.", work_order="WO-DEMO-021" if index%3 else "", photo=photo(EXAMPLES[index%5][4]), submitted_by=users["auditee"], status="DONE" if index%4==1 else "", verified_by=users["committee"] if index%4==1 else None, committee_note="Foto demonstrasi; bukan bukti operasional.")
            Audit.objects.create(area=areas[2], period=month, auditor=users["auditor"], due_date=month.replace(day=10))
            for index, days in enumerate([97,82,15]):
                RedTag.objects.create(area=areas[index], name=["Suku cadang pompa bekas","Pallet kayu rusak","Peralatan tidak terpakai"][index], reason="Barang perlu keputusan pemanfaatan atau pemindahan.", location="Area penampungan red tag", registered_on=timezone.localdate()-timedelta(days=days), photo=photo("cluttered-spare-parts.webp"), created_by=users["auditee"])
            Activity.objects.create(unit=unit, actor=users["committee"], text="Komite menetapkan 3 temuan wajib diperiksa ulang; semua temuan bulan sebelumnya tetap tersedia.")
        escalate_overdue()
        self.stdout.write(self.style.SUCCESS("Demo siap. Buka /login/ dan pilih salah satu dari lima peran. Semua nama/data/foto adalah ilustrasi."))
