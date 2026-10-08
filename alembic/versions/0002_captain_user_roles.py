"""Persist the captain role for existing team creators."""

from alembic import op

revision = "0002_captain_user_roles"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE users
        SET role = 'captain'
        WHERE role = 'participant'
          AND id IN (
              SELECT captain_id
              FROM teams
              WHERE captain_id IS NOT NULL
          )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE users
        SET role = 'participant'
        WHERE role = 'captain'
          AND id IN (
              SELECT captain_id
              FROM teams
              WHERE captain_id IS NOT NULL
          )
        """
    )
