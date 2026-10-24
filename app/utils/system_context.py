SYSTEM_CONTEXT = """\
The First Mutual Life Assurance Company Requisition System manages payment requisitions.

Users: new accounts register and stay inactive until an administrator activates them. Each user has a role (user, reviewer, approver, superuser) and flags: can initiate, can review, can approve, senior approver. Users upload a signature in their profile; a signature is required before creating a requisition.

Requisition: holds payee (in favor of), bank, branch, account number, reason for payment, ITF 263 (Yes/No/NA), currency (default USD), line items (account name, code, location, department, details, debit, credit) and totals. Numbers look like FML-REQ-YYYYMMDD-0001.

Workflow:
1. An initiator creates a requisition; it goes to pending_review.
2. A reviewer approves it (status pending_approval) or rejects it (rejected).
3. Approvers approve in sequence. After the first approval the status is partially_approved; when all required approvals are done it is approved. Any rejection requires a reason, sets it to rejected and returns it to the initiator, who can edit and resubmit it (it goes back to pending_review and the approvals restart).

Statuses: draft, pending_review, pending_approval, partially_approved, approved, rejected.

Approval thresholds: a USD requisition with total debit of 5000 or more needs 3 approvals; otherwise 2. The third approval must come from a senior approver.

Other features: search, lists, reports with export, print view with verification code, download formats, and batching of approved payments (one currency per batch, CSV or Excel) available to superusers, reviewers and approvers. Superusers manage users and view audit logs.
"""
