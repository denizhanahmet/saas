"""add admin user as superadmin

Revision ID: set_admin_superadmin
Revises: 
Create Date: 2025-10-16
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'set_admin_superadmin'
down_revision = '71e1355d0d81'
branch_labels = None
depends_on = None

def upgrade():
    op.execute("UPDATE user SET is_superadmin=1 WHERE username='admin'")

def downgrade():
    pass