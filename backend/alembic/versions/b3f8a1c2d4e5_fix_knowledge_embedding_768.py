"""Align knowledge_base.embedding with Gemini text-embedding-004 (768 dims)

Revision ID: b3f8a1c2d4e5
Revises: 918a6129a5c6
Create Date: 2026-04-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector


revision: str = "b3f8a1c2d4e5"
down_revision: Union[str, Sequence[str], None] = "918a6129a5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("knowledge_base", "embedding")
    op.add_column(
        "knowledge_base",
        sa.Column(
            "embedding",
            pgvector.sqlalchemy.vector.VECTOR(dim=768),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("knowledge_base", "embedding")
    op.add_column(
        "knowledge_base",
        sa.Column(
            "embedding",
            pgvector.sqlalchemy.vector.VECTOR(dim=1536),
            nullable=True,
        ),
    )
