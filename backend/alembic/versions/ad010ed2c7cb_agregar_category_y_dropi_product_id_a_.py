"""agregar category y dropi_product_id a products

Revision ID: ad010ed2c7cb
Revises: f2a9d5e7c1b8
Create Date: 2026-07-24 15:18:37.024440

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ad010ed2c7cb'
down_revision: Union[str, Sequence[str], None] = 'f2a9d5e7c1b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # category y dropi_product_id ya existen en algunos entornos (agregadas a mano
    # antes de que existiera esta migración) — se agregan solo si faltan, para que
    # esta revisión sea segura tanto en un entorno nuevo como en uno ya parchado.
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = {c['name'] for c in inspector.get_columns('products')}
    existing_indexes = {i['name'] for i in inspector.get_indexes('products')}

    if 'category' not in existing_columns:
        op.add_column('products', sa.Column('category', sa.String(), nullable=True))
    if 'dropi_product_id' not in existing_columns:
        op.add_column('products', sa.Column('dropi_product_id', sa.String(), nullable=True))
    if op.f('ix_products_category') not in existing_indexes:
        op.create_index(op.f('ix_products_category'), 'products', ['category'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_products_category'), table_name='products')
    op.drop_column('products', 'dropi_product_id')
    op.drop_column('products', 'category')
