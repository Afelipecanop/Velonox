"""orders user_id nullable

Revision ID: 8d33da579547
Revises: 0825a683cd04
Create Date: 2026-08-19 22:52:46.918000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8d33da579547'
down_revision: Union[str, Sequence[str], None] = '0825a683cd04'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # orders.user_id se creó NOT NULL en la migración inicial (ff0162fd9e2e), pero
    # models/order.py ya lo declara nullable=True desde hace tiempo — nunca se
    # había migrado la DB real para que coincidiera. Se necesita nullable para que
    # un checkout de invitado con un email que ya tiene cuenta pueda dejar la
    # orden sin asociar a esa cuenta real (routes/guest_checkout.py), en vez de
    # asociarla sin verificar que quien hace el checkout es el dueño del correo.
    op.alter_column('orders', 'user_id', existing_type=sa.UUID(), nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('orders', 'user_id', existing_type=sa.UUID(), nullable=False)
