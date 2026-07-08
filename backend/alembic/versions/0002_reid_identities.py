"""reid: identities gallery table + tracks.embedding/identity_id

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-08
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "identities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("embedding", sa.JSON(), nullable=False),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("track_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_identities_first_seen", "identities", ["first_seen"])
    op.create_index("ix_identities_last_seen", "identities", ["last_seen"])

    op.add_column("tracks", sa.Column("embedding", sa.JSON(), nullable=True))
    op.add_column("tracks", sa.Column("identity_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_tracks_identity_id",
        "tracks",
        "identities",
        ["identity_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_tracks_identity_id", "tracks", ["identity_id"])


def downgrade() -> None:
    op.drop_index("ix_tracks_identity_id", table_name="tracks")
    op.drop_constraint("fk_tracks_identity_id", "tracks", type_="foreignkey")
    op.drop_column("tracks", "identity_id")
    op.drop_column("tracks", "embedding")
    op.drop_index("ix_identities_last_seen", table_name="identities")
    op.drop_index("ix_identities_first_seen", table_name="identities")
    op.drop_table("identities")
