import shutil
import tempfile
import uuid
from datetime import date, timedelta
from io import BytesIO
from unittest.mock import patch
from PIL import Image
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from .models import *
from .services import *
from .permissions import can_edit_audit

def image_file():
    buffer = BytesIO()
    Image.new("RGB", (30,30), "red").save(buffer, "JPEG")
    return SimpleUploadedFile("photo.jpg", buffer.getvalue(), content_type="image/jpeg")

class WorkflowTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media = tempfile.mkdtemp()
        cls.media_setting = override_settings(MEDIA_ROOT=cls.media)
        cls.media_setting.enable()
    @classmethod
    def tearDownClass(cls):
        cls.media_setting.disable()
        shutil.rmtree(cls.media)
        super().tearDownClass()
    def setUp(self):
        self.unit = Unit.objects.create(name="Unit A")
        self.other_unit = Unit.objects.create(name="Unit B")
        self.users = {}
        for role,_ in ROLES:
            u=get_user_model().objects.create_user(username=role,password="test-password-long")
            Membership.objects.create(user=u,unit=self.unit,role=role)
            self.users[role]=u
        self.other=get_user_model().objects.create_user(username="other",password="test-password-long")
        Membership.objects.create(user=self.other,unit=self.other_unit,role="committee")
        self.area=Area.objects.create(unit=self.unit,name="Refinery")
        self.area.pics.add(self.users["auditee"])
        self.question=Question.objects.create(pillar="ringkas",text="Ada barang tidak diperlukan?")
        self.previous=Audit.objects.create(area=self.area,period=date(2026,9,1),due_date=date(2026,9,10),auditor=self.users["auditor"],status="SUBMITTED")
        self.old=self.finding(self.previous)
        self.audit=Audit.objects.create(area=self.area,period=date(2026,10,1),due_date=date(2026,10,10),auditor=self.users["auditor"])
        prepare_reviews(self.audit)
        self.review=self.audit.reviews.get()
        self.review.required=True;self.review.save()
    def finding(self,audit=None,**kwargs):
        return Finding.objects.create(audit=audit or self.audit,question=self.question,location="Zona A",description="Barang di lantai",photo=image_file(),**kwargs)
    def act_as(self,role): self.client.force_login(self.users[role])
    def test_submission_requires_20_and_required_reviews(self):
        for _ in range(19): self.finding()
        with self.assertRaises(ValidationError): submit_audit(self.users["auditor"],self.audit)
        self.finding()
        with self.assertRaises(ValidationError): submit_audit(self.users["auditor"],self.audit)
        review_previous(self.users["auditor"],self.review,"HANDLED","Sudah rapi",image_file(),0)
        submit_audit(self.users["auditor"],self.audit)
        self.audit.refresh_from_db();self.assertEqual(self.audit.status,"SUBMITTED")
    def test_recurrence_not_part_of_twenty_new(self):
        review_previous(self.users["auditor"],self.review,"EXISTS","Masih ada",image_file(),0)
        self.assertEqual(audit_readiness(self.audit)["new_count"],0)
        self.assertEqual(self.audit.findings.get().source,self.old)
    def test_review_conflict_and_reversal(self):
        review_previous(self.users["auditor"],self.review,"EXISTS","",image_file(),0)
        with self.assertRaises(ValidationError): review_previous(self.users["auditor"],self.review,"HANDLED","",image_file(),0)
        review_previous(self.users["auditor"],self.review,"HANDLED","",image_file(),1)
        self.assertFalse(self.audit.findings.exists())
    def test_cross_area_auditor(self):
        self.area.pics.add(self.users["auditor"])
        with self.assertRaises(ValidationError): self.audit.full_clean()
        self.assertFalse(can_edit_audit(self.users["auditor"], self.audit))
    def test_only_owner_can_edit_new_draft_finding(self):
        finding = self.finding()
        url = f"/temuan/{finding.pk}/edit/"
        data = {"question": self.question.pk, "location": "Zona B", "description": "Temuan diperbarui"}
        self.act_as("auditee")
        self.assertEqual(self.client.post(url, data).status_code, 403)
        self.act_as("auditor")
        self.assertEqual(self.client.post(url, data).status_code, 302)
        finding.refresh_from_db()
        self.assertEqual(finding.location, "Zona B")
        self.audit.status = "SUBMITTED"; self.audit.save()
        self.assertEqual(self.client.post(url, data).status_code, 403)
    def test_priority_and_status_are_committee_only(self):
        self.act_as("auditor")
        response=self.client.post(f"/temuan/{self.old.pk}/",{"action":"priority","priority":"HIGH"})
        self.assertEqual(response.status_code,403)
        self.act_as("committee")
        self.client.post(f"/temuan/{self.old.pk}/",{"action":"priority","priority":"HIGH"})
        self.old.refresh_from_db();self.assertEqual(self.old.priority,"HIGH")
    def test_progress_requires_work_order(self):
        self.old.priority="LOW";self.old.save()
        capa=FollowUp.objects.create(finding=self.old,corrective="Menunggu material")
        self.act_as("committee")
        self.client.post(f"/temuan/{self.old.pk}/",{"action":"verify","status":"PROGRESS","note":"Ada rencana"})
        capa.refresh_from_db();self.assertEqual(capa.status,"")
        capa.work_order="WO-123";capa.save()
        self.client.post(f"/temuan/{self.old.pk}/",{"action":"verify","status":"PROGRESS","note":"WO tersedia"})
        capa.refresh_from_db();self.assertEqual(capa.status,"PROGRESS")
    def test_done_requires_photo_and_action(self):
        self.old.priority="LOW";self.old.save()
        self.act_as("committee")
        self.client.post(f"/temuan/{self.old.pk}/",{"action":"verify","status":"DONE","note":"Selesai"})
        self.assertFalse(FollowUp.objects.filter(finding=self.old,status="DONE").exists())
    def test_other_unit_cannot_view_or_modify(self):
        self.client.force_login(self.other)
        for url in [f"/audit/{self.audit.pk}/",f"/temuan/{self.old.pk}/",f"/evidence/finding/{self.old.pk}/"]:
            self.assertEqual(self.client.get(url).status_code,404)
    def test_prior_photos_available_to_current_assignee(self):
        new=get_user_model().objects.create_user(username="new-auditor")
        Membership.objects.create(user=new,unit=self.unit,role="auditor")
        self.audit.auditor=new;self.audit.save()
        self.client.force_login(new)
        response=self.client.get(f"/evidence/finding/{self.old.pk}/")
        self.assertEqual(response.status_code,200)
        response.close()
    def test_redtag_deadline_and_escalation_idempotency(self):
        day=timezone.localdate()
        tag=RedTag.objects.create(area=self.area,name="Pompa",reason="Bekas",location="Rak",photo=image_file(),registered_on=day-timedelta(days=91),created_by=self.users["auditee"])
        self.assertEqual(tag.due_date,day-timedelta(days=1))
        self.assertEqual(escalate_overdue(),1);self.assertEqual(escalate_overdue(),0)
        self.assertEqual(Activity.objects.filter(text__contains="eskalasi").count(),1)
        self.act_as("management")
        self.assertEqual(self.client.get(f"/redtag/{tag.pk}/").status_code,404)
    def test_day_90_not_overdue(self):
        tag=RedTag.objects.create(area=self.area,name="Pallet",reason="Rusak",location="Rak",photo=image_file(),registered_on=timezone.localdate()-timedelta(days=90),created_by=self.users["auditee"])
        self.assertFalse(tag.overdue)
        self.assertEqual(escalate_overdue(),0)
    def test_api_duplicate_safe(self):
        self.act_as("auditor")
        op=uuid.uuid4()
        payload={"operation":str(op),"user":self.users["auditor"].pk,"kind":"finding","question":self.question.pk,"location":"Zona A","description":"Draf offline"}
        first=self.client.post(f"/api/audit/{self.audit.pk}/sync/",payload|{"photo":image_file()})
        self.assertEqual(first.status_code,200,first.content)
        second=self.client.post(f"/api/audit/{self.audit.pk}/sync/",payload|{"photo":image_file()})
        self.assertEqual(second.status_code,200)
        self.assertEqual(Finding.objects.filter(pk=op).count(),1)
        self.assertEqual(SyncReceipt.objects.filter(pk=op).count(),1)
    def test_sync_rejects_changed_identity_and_locked_audit(self):
        self.act_as("auditor")
        payload={"operation":str(uuid.uuid4()),"user":self.other.pk,"kind":"finding"}
        self.assertEqual(self.client.post(f"/api/audit/{self.audit.pk}/sync/",payload).status_code,403)
        self.audit.status="SUBMITTED";self.audit.save()
        payload["user"]=self.users["auditor"].pk
        self.assertEqual(self.client.post(f"/api/audit/{self.audit.pk}/sync/",payload).status_code,409)
    def test_evidence_requires_login(self):
        self.assertEqual(self.client.get(f"/evidence/finding/{self.old.pk}/").status_code,302)
    def test_scoring_missing_is_not_no_progress(self):
        fresh=self.finding()
        summary=score_summary([fresh])
        self.assertIsNone(summary["main"]);self.assertEqual(summary["pending"],1)
        FollowUp.objects.create(finding=fresh,status="DONE")
        self.assertEqual(score_summary([Finding.objects.get(pk=fresh.pk)])["main"],100)
    def test_invalid_photo_rejected(self):
        with self.assertRaises(ValidationError): clean_photo(SimpleUploadedFile("x.jpg",b"not an image"))
    def test_pages_render_for_all_roles(self):
        for role,_ in ROLES:
            self.act_as(role)
            for url in ["/","/audit/","/tindak-lanjut/","/redtag/","/jadwal/"]:
                response=self.client.get(url)
                self.assertEqual(response.status_code,200,(role,url,response.content[:200]))
        self.act_as("committee")
        for url in [f"/audit/{self.audit.pk}/",f"/temuan/{self.old.pk}/","/laporan/"]:
            self.assertEqual(self.client.get(url).status_code,200)
    @override_settings(DEBUG=False,DEMO_MODE=False)
    def test_demo_login_disabled_for_production(self):
        self.assertEqual(self.client.post("/demo-login/",{"role":"committee"}).status_code,404)
