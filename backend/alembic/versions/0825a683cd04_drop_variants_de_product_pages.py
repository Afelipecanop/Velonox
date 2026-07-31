"""drop variants de product_pages

Revision ID: 0825a683cd04
Revises: ad010ed2c7cb
Create Date: 2026-07-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0825a683cd04'
down_revision: Union[str, Sequence[str], None] = 'ad010ed2c7cb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # product_pages nunca se creó vía Alembic (tabla agregada a mano, como
    # category/dropi_product_id en products) - defensivo por si el entorno no
    # la tiene, igual que ad010ed2c7cb con products.
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'product_pages' in inspector.get_table_names():
        existing_columns = {c['name'] for c in inspector.get_columns('product_pages')}
        if 'variants' in existing_columns:
            op.drop_column('product_pages', 'variants')


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'product_pages' in inspector.get_table_names():
        existing_columns = {c['name'] for c in inspector.get_columns('product_pages')}
        if 'variants' not in existing_columns:
            op.add_column('product_pages', sa.Column('variants', sa.Text(), nullable=True))
