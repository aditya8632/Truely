from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0001_init_grants_svc"
down_revision = None
branch_labels = None
depends_on = None

SCHEMA = "grants_svc"


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")

    # Permission ENUM
    op.execute(
        f"""
DO $$
BEGIN
    CREATE TYPE {SCHEMA}.permission_enum AS ENUM ('view','edit','admin');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END
$$;
"""
    )

    # users
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.UniqueConstraint("name", name="uq_users_name"),
        schema=SCHEMA,
    )

    # documents
    op.create_table(
        "documents",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.UniqueConstraint("title", name="uq_documents_title"),
        schema=SCHEMA,
    )

    # grants
    op.create_table(
        "grants",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "document_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.documents.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "granted_to_user_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "granted_by_user_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("permission", sa.Enum(name="permission_enum", schema=SCHEMA), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema=SCHEMA,
    )

    # Indexes
    op.create_index("ix_grants_document_id", "grants", ["document_id"], schema=SCHEMA)
    op.create_index("ix_grants_granted_to_user_id", "grants", ["granted_to_user_id"], schema=SCHEMA)
    op.create_index("ix_grants_expires_at", "grants", ["expires_at"], schema=SCHEMA)

    # Only one non-revoked grant per (granted_to_user_id, document_id).
    # The service also enforces the full "active" definition (expires_at > now) for correctness.
    op.create_index(
        "uq_active_grant_per_pair",
        "grants",
        ["granted_to_user_id", "document_id"],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )

    # Deterministic seed data
    alice = "11111111-1111-1111-1111-111111111111"
    bob = "22222222-2222-2222-2222-222222222222"
    carol = "33333333-3333-3333-3333-333333333333"

    q1_report = "44444444-4444-4444-4444-444444444444"
    product_roadmap = "55555555-5555-5555-5555-555555555555"
    budget_2026 = "66666666-6666-6666-6666-666666666666"

    op.execute(
        f"""
INSERT INTO {SCHEMA}.users (id, name) VALUES
('{alice}', 'Alice'),
('{bob}', 'Bob'),
('{carol}', 'Carol')
ON CONFLICT (id) DO NOTHING;
"""
    )

    op.execute(
        f"""
INSERT INTO {SCHEMA}.documents (id, title) VALUES
('{q1_report}', 'Q1 Report'),
('{product_roadmap}', 'Product Roadmap'),
('{budget_2026}', 'Budget 2026')
ON CONFLICT (id) DO NOTHING;
"""
    )


def downgrade() -> None:
    op.drop_index("uq_active_grant_per_pair", table_name="grants", schema=SCHEMA)
    op.drop_index("ix_grants_expires_at", table_name="grants", schema=SCHEMA)
    op.drop_index("ix_grants_granted_to_user_id", table_name="grants", schema=SCHEMA)
    op.drop_index("ix_grants_document_id", table_name="grants", schema=SCHEMA)

    op.drop_table("grants", schema=SCHEMA)
    op.drop_table("documents", schema=SCHEMA)
    op.drop_table("users", schema=SCHEMA)

    op.execute(f"DROP TYPE IF EXISTS {SCHEMA}.permission_enum")
