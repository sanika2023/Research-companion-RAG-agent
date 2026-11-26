"""store original PDFs in the database instead of UPLOAD_DIR

Revision ID: 0002
Revises: 0001
"""

import os
import uuid
from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    files = op.create_table(
        "document_files",
        sa.Column(
            "doc_id",
            sa.Uuid(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("data", sa.LargeBinary(), nullable=False),
    )
    _import_saved_pdfs(files)


def _import_saved_pdfs(files: sa.Table) -> None:
    # Before 0002, PDFs were saved as UPLOAD_DIR/<doc_id>.pdf (relative to backend/).
    upload_dir = Path(os.environ.get("UPLOAD_DIR", "data/uploads"))
    conn = op.get_bind()
    for doc_id in conn.execute(sa.text("SELECT id FROM documents")).scalars():
        path = upload_dir / f"{uuid.UUID(str(doc_id))}.pdf"
        if path.is_file():
            conn.execute(files.insert().values(doc_id=doc_id, data=path.read_bytes()))


def downgrade() -> None:
    op.drop_table("document_files")
