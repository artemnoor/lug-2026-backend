"""Create the explicit LUG domain schema.

The rebuild starts from a relational schema whose core identity, ownership and
workflow fields are columns and constraints. JSON is retained only for
extensible settings and review criteria.
"""

import sqlalchemy as sa
from alembic import op

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Team.captain_id is intentionally not a foreign key. A team and its first
    # captain are created in one application transaction, while User.team_id
    # remains a strict foreign key.
    op.create_table(
        "teams",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("group", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=False),
        sa.Column("captain_id", sa.String(length=64), nullable=True),
        sa.Column("invite_code", sa.String(length=80), nullable=False),
        sa.Column("invite_status", sa.String(length=32), nullable=False),
        sa.Column("invite_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("member_limit", sa.Integer(), nullable=False),
        sa.Column("flag_url", sa.String(length=500), nullable=False),
        sa.Column("quota_confirmed", sa.Boolean(), nullable=False),
        sa.Column("is_admitted", sa.Boolean(), nullable=False),
        sa.Column("review_name_status", sa.String(length=32), nullable=False),
        sa.Column("review_group_status", sa.String(length=32), nullable=False),
        sa.Column("review_flag_status", sa.String(length=32), nullable=False),
        sa.Column("review_description_status", sa.String(length=32), nullable=False),
        sa.Column("review_comment", sa.Text(), nullable=False),
        sa.Column("video_url", sa.String(length=1000), nullable=False),
        sa.Column("video_file_url", sa.String(length=500), nullable=False),
        sa.Column("video_status", sa.String(length=32), nullable=False),
        sa.Column("video_comment", sa.Text(), nullable=False),
        sa.Column("video_score", sa.Float(), nullable=True),
        sa.Column("video_criteria_scores", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("group"),
        sa.UniqueConstraint("invite_code"),
    )
    op.create_index("ix_teams_invite", "teams", ["invite_code", "invite_status"])
    op.create_index(
        "ix_teams_review",
        "teams",
        ["review_name_status", "review_group_status", "review_flag_status"],
    )
    op.create_index("ix_teams_captain_id", "teams", ["captain_id"])

    op.create_table(
        "users",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("fio", sa.String(length=200), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("messenger", sa.String(length=32), nullable=False),
        sa.Column("messenger_contact", sa.String(length=128), nullable=False),
        sa.Column("telegram_account", sa.String(length=128), nullable=False),
        sa.Column("team_id", sa.String(length=64), nullable=True),
        sa.Column("email_verified", sa.Boolean(), nullable=False),
        sa.Column("identity_status", sa.String(length=32), nullable=False),
        sa.Column("identity_comment", sa.Text(), nullable=False),
        sa.Column("avatar_url", sa.String(length=500), nullable=False),
        sa.Column("student_card_file", sa.String(length=500), nullable=False),
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("phone"),
    )
    op.create_index("ix_users_email_lower", "users", ["email"])
    op.create_index("ix_users_identity_status", "users", ["identity_status"])
    op.create_index("ix_users_team_id", "users", ["team_id"])

    op.create_table(
        "uploads",
        sa.Column("upload_id", sa.String(length=80), nullable=False),
        sa.Column("owner_user_id", sa.String(length=64), nullable=True),
        sa.Column("claim_subject", sa.String(length=128), nullable=True),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("storage_path", sa.String(length=1000), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("content_type", sa.String(length=160), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("scan_status", sa.String(length=32), nullable=False),
        sa.Column("scan_reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("upload_id"),
        sa.UniqueConstraint("url"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index("ix_uploads_owner_status", "uploads", ["owner_user_id", "status", "scan_status"])
    op.create_index("ix_uploads_claim", "uploads", ["claim_subject", "created_at"])
    op.create_index("ix_uploads_owner_user_id", "uploads", ["owner_user_id"])
    op.create_index("ix_uploads_claim_subject", "uploads", ["claim_subject"])

    op.create_table(
        "achievements",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("direction", sa.String(length=32), nullable=False),
        sa.Column("category", sa.String(length=120), nullable=False),
        sa.Column("details", sa.String(length=2000), nullable=False),
        sa.Column("file_url", sa.String(length=500), nullable=False),
        sa.Column("file_upload_id", sa.String(length=80), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("points", sa.Float(), nullable=True),
        sa.Column("review_comment", sa.Text(), nullable=False),
        sa.Column("reviewed_by", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["file_upload_id"], ["uploads.upload_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_achievements_status", "achievements", ["status", "updated_at"])
    op.create_index("ix_achievements_user_id", "achievements", ["user_id"])

    op.create_table(
        "notifications",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message", sa.String(length=4000), nullable=False),
        sa.Column("email_requested", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_notifications_target_time", "notifications", ["target_type", "target_id", "created_at"]
    )

    op.create_table(
        "notification_reads",
        sa.Column("notification_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["notification_id"], ["notifications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("notification_id", "user_id"),
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_agent", sa.String(length=500), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"])

    op.create_table(
        "email_verifications",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", "purpose", name="uq_email_verifications_email_purpose"),
    )
    op.create_index("ix_email_verifications_email", "email_verifications", ["email"])
    op.create_index("ix_email_verifications_expires_at", "email_verifications", ["expires_at"])

    op.create_table(
        "password_resets",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_password_resets_email", "password_resets", ["email"])
    op.create_index("ix_password_resets_expires_at", "password_resets", ["expires_at"])

    op.create_table(
        "audit_log",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("actor_user_id", sa.String(length=64), nullable=True),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=80), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_log_actor_user_id", "audit_log", ["actor_user_id"])
    op.create_index("ix_audit_log_at", "audit_log", ["at"])

def downgrade() -> None:
    op.drop_index("ix_audit_log_at", table_name="audit_log")
    op.drop_index("ix_audit_log_actor_user_id", table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_index("ix_password_resets_expires_at", table_name="password_resets")
    op.drop_index("ix_password_resets_email", table_name="password_resets")
    op.drop_table("password_resets")
    op.drop_index("ix_email_verifications_expires_at", table_name="email_verifications")
    op.drop_index("ix_email_verifications_email", table_name="email_verifications")
    op.drop_table("email_verifications")
    op.drop_index("ix_sessions_expires_at", table_name="sessions")
    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_table("sessions")
    op.drop_table("notification_reads")
    op.drop_index("ix_notifications_target_time", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("ix_achievements_user_id", table_name="achievements")
    op.drop_index("ix_achievements_status", table_name="achievements")
    op.drop_table("achievements")
    op.drop_index("ix_uploads_claim_subject", table_name="uploads")
    op.drop_index("ix_uploads_owner_user_id", table_name="uploads")
    op.drop_index("ix_uploads_claim", table_name="uploads")
    op.drop_index("ix_uploads_owner_status", table_name="uploads")
    op.drop_table("uploads")
    op.drop_index("ix_users_team_id", table_name="users")
    op.drop_index("ix_users_identity_status", table_name="users")
    op.drop_index("ix_users_email_lower", table_name="users")
    op.drop_table("users")
    op.drop_index("ix_teams_captain_id", table_name="teams")
    op.drop_index("ix_teams_review", table_name="teams")
    op.drop_index("ix_teams_invite", table_name="teams")
    op.drop_table("teams")
    op.drop_table("settings")
