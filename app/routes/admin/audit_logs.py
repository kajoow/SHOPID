"""Route blueprint untuk melihat audit trail / log aktivitas sistem (Bab 14.6)."""
from flask import Blueprint, render_template, request
from ...utils.decorators import login_required, admin_required
from ...repositories import audit_repo, user_repo

admin_audit_bp = Blueprint("admin_audit", __name__, url_prefix="/admin")


@admin_audit_bp.route("/audit-logs", methods=["GET"])
@login_required
@admin_required
def list_audit_logs():
    """Halaman penelusuran audit log sistem (Bab 14.6)."""
    action = request.args.get("action")
    entity_type = request.args.get("entity_type")
    page = request.args.get("page", 1, type=int)
    per_page = 25

    query = {}
    if action:
        query["action"] = action
    if entity_type:
        query["entity_type"] = entity_type

    total = audit_repo.count(query)
    skip = (page - 1) * per_page
    logs = audit_repo.find_all(query, skip=skip, limit=per_page)

    # Populasi nama actor
    enriched = []
    for l in logs:
        actor = user_repo.find_by_id(l.get("actor_id"))
        enriched.append({
            **l,
            "actor_name": actor.get("name") if actor else "-",
            "actor_email": actor.get("email") if actor else "-",
        })

    return render_template(
        "admin/audit_logs.html",
        active="audit-logs",
        logs=enriched,
        action=action or "",
        entity_type=entity_type or "",
        page=page,
        total=total,
        total_pages=(total + per_page - 1) // per_page if total > 0 else 1,
    )

