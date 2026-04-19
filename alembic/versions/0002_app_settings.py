"""add app_settings singleton

Revision ID: 0002_app_settings
Revises: 0001_initial
Create Date: 2026-04-19 00:00:01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_app_settings"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("anthropic_api_key_ct", sa.Text, nullable=True),
        sa.Column("anthropic_model", sa.String(60), nullable=True),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    # Ensure a singleton row always exists.
    op.execute("INSERT INTO app_settings (id) VALUES (1)")


def downgrade() -> None:
    op.drop_table("app_settings")
