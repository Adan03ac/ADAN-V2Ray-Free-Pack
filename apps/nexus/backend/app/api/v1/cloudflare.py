"""Cloudflare module: architecturally prepared, explicitly not enabled.

No account is connected, no deployment is performed, and no usage metric is
invented. Wiring real deployments requires an operator-provided scoped token and
explicit authorization, per the specification.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, client_ip, require_auth, require_csrf
from app.core.config import settings
from app.core.db import get_db
from app.models import Deployment
from app.services import audit

router = APIRouter(prefix="/cloudflare", tags=["cloudflare"])

CONSIDERATIONS = [
    "Cloudflare Workers/Pages free plans have daily request and build quotas; they are not unlimited.",
    "Deploying proxy configurations may violate Cloudflare's terms of service; the operator must review them.",
    "A scoped API token (Workers Scripts:Edit, Account Settings:Read) is required; never store it in the browser.",
    "Third-party panel projects (BPB Worker Panel, BPB Wizard, Nova Proxy) carry their own licenses. "
    "No third-party code is copied or redistributed by this module.",
    "Deployment actions must be explicitly authorized by an administrator and are audited.",
]


@router.get("/status")
def cloudflare_status(
    context: AuthContext = Depends(require_auth), db: Session = Depends(get_db)
) -> dict:
    configured = bool(settings.cloudflare_enabled and settings.cloudflare_account_id and settings.cloudflare_api_token)
    deployments = db.execute(select(Deployment).order_by(desc(Deployment.created_at)).limit(20)).scalars().all()
    return {
        "configured": configured,
        "enabled_by_flag": settings.cloudflare_enabled,
        "account_id_present": bool(settings.cloudflare_account_id),
        "token_present": bool(settings.cloudflare_api_token),
        "status": "configured" if configured else "not_configured",
        "message": (
            "Cloudflare credentials are present, but deployment operations are not implemented in this build. "
            "Nothing will be deployed."
            if configured
            else "No Cloudflare account is connected. This module is a prepared interface, not an active integration."
        ),
        "capabilities": {
            "worker_deploy": False,
            "pages_deploy": False,
            "rollback": False,
            "secret_management": False,
            "deployment_logs": False,
            "account_metrics": False,
            "bpb_compatibility": False,
        },
        "planned_capabilities": [
            "Scoped API token storage in the server environment only",
            "Worker and Pages deployment with version history",
            "Rollback to a previous version",
            "Deployment log stream with redaction",
            "Subscription endpoint binding",
        ],
        "considerations": CONSIDERATIONS,
        "deployments": [
            {
                "id": row.id,
                "provider": row.provider,
                "target": row.target,
                "environment": row.environment,
                "status": row.status,
                "version": row.version,
                "note": row.note,
                "deployed_at": row.deployed_at,
                "created_at": row.created_at,
            }
            for row in deployments
        ],
        "research": {
            "bpb_worker_panel": "Interface concepts only; license review required before any integration.",
            "bpb_wizard_android": "Not integrated. Mobile wizard flows are out of scope for the MVP.",
            "nova_proxy": "Conceptual reference for subscription endpoints; no code reused.",
        },
        "quota_reference": "https://developers.cloudflare.com/workers/platform/limits/",
    }


@router.post("/deployments")
def request_deployment(
    request: Request,
    context: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> dict:
    audit.record(
        db,
        action="cloudflare.deploy_requested",
        user=context.user,
        outcome="rejected",
        ip_address=client_ip(request),
        detail={"reason": "deployment provider not implemented"},
    )
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "Deployment is not implemented in this build. Configure a scoped token and complete the "
            "authorization review before enabling this module."
        ),
    )
