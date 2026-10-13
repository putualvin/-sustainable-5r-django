from .models import Membership, Area, Audit, Finding, RedTag

def units_for(user, *roles):
    if not user.is_authenticated: return []
    qs = Membership.objects.filter(user=user)
    if roles: qs = qs.filter(role__in=roles)
    return qs.values_list("unit_id", flat=True)

def has_role(user, unit_id, *roles):
    return Membership.objects.filter(user=user, unit_id=unit_id, role__in=roles).exists()

def visible_areas(user):
    from django.db.models import Q
    units = units_for(user, "committee", "auditor", "redtag", "management")
    return Area.objects.filter(Q(unit_id__in=units) | Q(unit_id__in=units_for(user, "auditee"), pics=user)).distinct()

def visible_audits(user):
    from django.db.models import Q
    return Audit.objects.filter(Q(area__unit_id__in=units_for(user, "committee", "management")) |
        Q(auditor=user, area__unit_id__in=units_for(user, "auditor")) |
        Q(area__pics=user, area__unit_id__in=units_for(user, "auditee"))).distinct()

def visible_findings(user):
    return Finding.objects.filter(audit__in=visible_audits(user)).select_related("audit__area__unit", "question", "followup")

def visible_tags(user):
    from django.db.models import Q
    return RedTag.objects.filter(Q(area__unit_id__in=units_for(user, "committee", "redtag")) |
        Q(area__pics=user, area__unit_id__in=units_for(user, "auditee"))).distinct()

def can_edit_audit(user, audit):
    return (audit.status == "DRAFT" and audit.auditor_id == user.id
            and has_role(user, audit.area.unit_id, "auditor")
            and not audit.area.pics.filter(pk=user.pk).exists())
