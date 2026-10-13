from django.conf import settings
from .models import Membership, ROLES

def shell(request):
    roles = set(Membership.objects.filter(user=request.user).values_list("role", flat=True)) if request.user.is_authenticated else set()
    return {"role_labels": [label for role, label in ROLES if role in roles], "roles": roles,
            "demo_mode": settings.DEMO_MODE, "nav_audit": bool(roles & {"auditor", "committee"}),
            "nav_capa": bool(roles & {"auditee", "committee"}),
            "nav_redtag": bool(roles & {"auditee", "redtag", "committee"}),
            "nav_reports": bool(roles & {"management", "committee", "auditor"}),
            "is_committee": "committee" in roles}
