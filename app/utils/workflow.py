from __future__ import annotations

from typing import Any, Dict, List


def build_workflow(requisition, approval_logs) -> List[Dict[str, Any]]:
    """Build an ordered list of workflow stages for a requisition.

    Each stage dict has:
        - label: human-readable name of the stage
        - state: one of "done", "pending", "waiting", "rejected"
        - completed_by: full name of the user who completed the stage (or None)
        - completed_at: datetime when the stage was completed (or None)
        - eligible: list of full names of users eligible for this stage
    """
    from app.models import User

    stages: List[Dict[str, Any]] = []

    # Initiation stage is always first and considered done
    stages.append(
        {
            "label": "Initiated",
            "state": "done",
            "completed_by": getattr(requisition.initiator, "full_name", None),
            "completed_at": requisition.initiated_at,
            "eligible": [],
        }
    )

    # Review stage
    reviewers = [
        u.full_name
        for u in User.query.filter_by(can_review=True, is_active=True).all()
    ]
    review_stage: Dict[str, Any] = {
        "label": "Review",
        "state": "waiting",
        "completed_by": None,
        "completed_at": None,
        "eligible": reviewers,
    }

    if requisition.reviewer:
        review_stage["state"] = "done"
        review_stage["completed_by"] = requisition.reviewer.full_name
        review_stage["completed_at"] = requisition.reviewed_at
    elif requisition.status == "rejected":
        review_stage["state"] = "rejected"
    elif requisition.status == "pending_review":
        review_stage["state"] = "pending"

    stages.append(review_stage)

    # Approval stages
    approvers = [
        u.full_name
        for u in User.query.filter_by(can_approve=True, is_active=True).all()
    ]
    senior_approvers = [
        u.full_name
        for u in User.query.filter_by(
            is_senior_approver=True, is_active=True
        ).all()
    ]

    approved_logs = {
        log.approval_level: log
        for log in approval_logs
        if log.action == "approved"
    }
    rejected_levels = {
        log.approval_level
        for log in approval_logs
        if log.action == "rejected"
    }

    total_levels = requisition.required_approvals or 0
    levels = range(1, total_levels + 1)
    pending_levels = [lvl for lvl in levels if lvl not in approved_logs]
    next_level = pending_levels[0] if pending_levels else None

    for level in levels:
        if level == 3:
            label = "Senior Approver (3rd)"
            eligible = senior_approvers
        else:
            label = f"Approver {level}"
            eligible = approvers

        stage: Dict[str, Any] = {
            "label": label,
            "state": "waiting",
            "completed_by": None,
            "completed_at": None,
            "eligible": eligible,
        }

        log = approved_logs.get(level)
        if log:
            stage["state"] = "done"
            stage["completed_by"] = getattr(log.approver, "full_name", None)
            stage["completed_at"] = log.created_at
        elif level in rejected_levels:
            stage["state"] = "rejected"
        elif (
            requisition.status in ("pending_approval", "partially_approved")
            and level == next_level
        ):
            stage["state"] = "pending"

        stages.append(stage)

    return stages
