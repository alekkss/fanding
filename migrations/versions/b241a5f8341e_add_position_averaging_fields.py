
"""add_position_averaging_fields

Revision ID: b241a5f8341e
Revises: d2141da78c5d
Create Date: 2026-01-07

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision = 'b241a5f8341e'
down_revision = 'd2141da78c5d'
branch_labels = None
depends_on = None


def upgrade():
    # Добавляем новые поля для усреднения цен при докупках
    op.add_column('positions', sa.Column('average_spot_entry_price', sa.Float(), nullable=True))
    op.add_column('positions', sa.Column('average_futures_entry_price', sa.Float(), nullable=True))
    op.add_column('positions', sa.Column('total_entries', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('positions', sa.Column('last_entry_spread_pct', sa.Float(), nullable=True))
    op.add_column('positions', sa.Column('last_addition_timestamp', sa.DateTime(), nullable=True))
    
    # Заполняем average_* для существующих позиций (миграция данных)
    op.execute("""
        UPDATE positions 
        SET average_spot_entry_price = spot_entry_price,
            average_futures_entry_price = futures_entry_price,
            last_entry_spread_pct = entry_spread_pct
        WHERE average_spot_entry_price IS NULL
    """)
    
    # Делаем поля NOT NULL после заполнения
    op.alter_column('positions', 'average_spot_entry_price', nullable=False)
    op.alter_column('positions', 'average_futures_entry_price', nullable=False)
    op.alter_column('positions', 'last_entry_spread_pct', nullable=False)


def downgrade():
    # Откат миграции
    op.drop_column('positions', 'last_addition_timestamp')
    op.drop_column('positions', 'last_entry_spread_pct')
    op.drop_column('positions', 'total_entries')
    op.drop_column('positions', 'average_futures_entry_price')
    op.drop_column('positions', 'average_spot_entry_price')
