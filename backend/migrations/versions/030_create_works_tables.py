"""create works tables

Revision ID: 030
Revises: 029
Create Date: 2026-07-06 09:50:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "030"
down_revision = "029"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "works",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("cover_object_key", sa.String(length=500), nullable=True),
        sa.Column("final_object_key", sa.String(length=500), nullable=False),
        sa.Column("source_canvas_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_canvas_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_generation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["source_canvas_id"], ["canvas_documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_canvas_item_id"], ["canvas_items.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_generation_id"], ["canvas_item_generations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_works_user_id", "works", ["user_id"])
    op.create_index("ix_works_status", "works", ["status"])
    op.create_index("ix_works_source_canvas_id", "works", ["source_canvas_id"])
    op.create_index("ix_works_source_canvas_item_id", "works", ["source_canvas_item_id"])
    op.create_index("ix_works_source_generation_id", "works", ["source_generation_id"])
    op.create_index("ix_works_final_object_key", "works", ["final_object_key"])
    op.create_index("ix_works_deleted_at", "works", ["deleted_at"])
    op.create_unique_constraint("uq_works_user_canvas_item_final", "works", ["user_id", "source_canvas_item_id", "final_object_key"])

    op.create_table(
        "work_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("work_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=30), nullable=False),
        sa.Column("object_key", sa.String(length=500), nullable=False),
        sa.Column("media_type", sa.String(length=20), nullable=False),
        sa.Column("source_canvas_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_canvas_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_generation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["work_id"], ["works.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_canvas_id"], ["canvas_documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_canvas_item_id"], ["canvas_items.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_generation_id"], ["canvas_item_generations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_work_items_work_id", "work_items", ["work_id"])
    op.create_index("ix_work_items_user_id", "work_items", ["user_id"])
    op.create_index("ix_work_items_role", "work_items", ["role"])
    op.create_index("ix_work_items_object_key", "work_items", ["object_key"])
    op.create_index("ix_work_items_media_type", "work_items", ["media_type"])
    op.create_index("ix_work_items_source_canvas_id", "work_items", ["source_canvas_id"])
    op.create_index("ix_work_items_source_canvas_item_id", "work_items", ["source_canvas_item_id"])
    op.create_index("ix_work_items_source_generation_id", "work_items", ["source_generation_id"])
    op.create_index("idx_work_items_work_role", "work_items", ["work_id", "role"])


def downgrade():
    op.drop_index("idx_work_items_work_role", table_name="work_items")
    op.drop_index("ix_work_items_source_generation_id", table_name="work_items")
    op.drop_index("ix_work_items_source_canvas_item_id", table_name="work_items")
    op.drop_index("ix_work_items_source_canvas_id", table_name="work_items")
    op.drop_index("ix_work_items_media_type", table_name="work_items")
    op.drop_index("ix_work_items_object_key", table_name="work_items")
    op.drop_index("ix_work_items_role", table_name="work_items")
    op.drop_index("ix_work_items_user_id", table_name="work_items")
    op.drop_index("ix_work_items_work_id", table_name="work_items")
    op.drop_table("work_items")

    op.drop_constraint("uq_works_user_canvas_item_final", "works", type_="unique")
    op.drop_index("ix_works_deleted_at", table_name="works")
    op.drop_index("ix_works_final_object_key", table_name="works")
    op.drop_index("ix_works_source_generation_id", table_name="works")
    op.drop_index("ix_works_source_canvas_item_id", table_name="works")
    op.drop_index("ix_works_source_canvas_id", table_name="works")
    op.drop_index("ix_works_status", table_name="works")
    op.drop_index("ix_works_user_id", table_name="works")
    op.drop_table("works")
