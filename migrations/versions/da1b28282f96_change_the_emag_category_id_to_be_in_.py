"""change the emag_category_id to be in the FitnessCategory model ; and add emag_product_category_name to the same model

Revision ID: da1b28282f96
Revises: c807c65ae200
Create Date: 2025-04-24 08:39:26.154671

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'da1b28282f96'
down_revision = 'c807c65ae200'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('fitness_categories', schema=None) as batch_op:
        batch_op.add_column(sa.Column('emag_category_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('emag_product_name_category', sa.String(length=255), nullable=True))

    with op.batch_alter_table('mappings', schema=None) as batch_op:
        batch_op.drop_column('emag_category_id')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('mappings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('emag_category_id', sa.INTEGER(), autoincrement=False, nullable=True))

    with op.batch_alter_table('fitness_categories', schema=None) as batch_op:
        batch_op.drop_column('emag_product_name_category')
        batch_op.drop_column('emag_category_id')

    # ### end Alembic commands ###
