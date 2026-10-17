def build_workflow(requisition, approval_logs):
    """Build an ordered list of workflow stages for a requisition."""
    from app.models import User

    stages = []

    stages.append({
        'label': 'Initiated',
        'state': 'done',
        'completed_by': requisition.initiator.full_name,
        'completed_at': requisition.initiated_at,
        'eligible': [],
    })

    reviewers = [u.full_name for u in User.query.filter_by(can_review=True, is_active=True).all()]
    review_stage = {
        'label': 'Review',
        'state': 'waiting',
        'completed_by': None,
        'completed_at': None,
        'eligible': reviewers,
    }
    if requisition.reviewer:
        review_stage['state'] = 'done'
        review_stage['completed_by'] = requisition.reviewer.full_name
        review_stage['completed_at'] = requisition.reviewed_at
    elif requisition.status == 'rejected':
        review_stage['state'] = 'rejected'
    elif requisition.status == 'pending_review':
        review_stage['state'] = 'pending'
    stages.append(review_stage)

    approvers = [u.full_name for u in User.query.filter_by(can_approve=True, is_active=True).all()]
    senior_approvers = [u.full_name for u in User.query.filter_by(is_senior_approver=True, is_active=True).all()]

    approved_logs = {log.approval_level: log for log in approval_logs if log.action == 'approved'}
    rejected_levels = {log.approval_level for log in approval_logs if log.action == 'rejected'}

    levels = range(1, requisition.required_approvals + 1)
    pending_levels = [lvl for lvl in levels if lvl not in approved_logs]
    next_level = pending_levels[0] if pending_levels else None

    for level in levels:
        if level == 3:
            label = 'Senior Approver (3rd)'
            eligible = senior_approvers
        else:
            label = f'Approver {level}'
            eligible = approvers

        stage = {
            'label': label,
            'state': 'waiting',
            'completed_by': None,
            'completed_at': None,
            'eligible': eligible,
        }
        log = approved_logs.get(level)
        if log:
            stage['state'] = 'done'
            stage['completed_by'] = log.approver.full_name
            stage['completed_at'] = log.created_at
        elif level in rejected_levels:
            stage['state'] = 'rejected'
        elif requisition.status in ['pending_approval', 'partially_approved'] and level == next_level:
            stage['state'] = 'pending'
        stages.append(stage)

    return stages
