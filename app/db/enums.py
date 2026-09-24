"""Persisted enum values shared by models and contracts."""

ROLE_PARTICIPANT = "participant"
ROLE_ADMIN = "admin"
USER_ROLES = (ROLE_PARTICIPANT, ROLE_ADMIN)
IDENTITY_STATUSES = ("pending", "approved", "rejected")
REVIEW_STATUSES = ("none", "pending", "approved", "rejected")
UPLOAD_STATUSES = ("pending", "uploaded", "scanning", "clean", "rejected")
UPLOAD_SCAN_STATUSES = ("pending", "clean", "rejected", "error")
NOTIFICATION_TARGETS = ("all", "teams", "team", "captains", "captain", "user", "admins")
