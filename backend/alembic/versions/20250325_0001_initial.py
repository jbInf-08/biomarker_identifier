"""Initial revision — schema managed by init_db / autogenerate in future.

Revision ID: 20250325_0001
Revises:
Create Date: 2025-03-25
"""

from typing import Sequence, Union

revision: str = "20250325_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply migration — baseline; tables may already exist from create_all."""
    pass


def downgrade() -> None:
    """Reverse migration."""
    pass
