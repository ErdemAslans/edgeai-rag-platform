"""Add edge_logs table with PostgreSQL partitioning

Revision ID: 003
Revises: 002
Create Date: 2026-01-01

"""
from typing import Sequence, Union
from datetime import datetime, timedelta

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the partitioned parent table for edge logs
    # Using raw SQL for partitioned table creation since Alembic's create_table
    # doesn't fully support PostgreSQL declarative partitioning syntax
    op.execute('''
        CREATE TABLE edge_logs (
            id UUID NOT NULL DEFAULT uuid_generate_v4(),
            timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
            source_id VARCHAR(100) NOT NULL,
            level VARCHAR(20) NOT NULL,
            message TEXT NOT NULL,
            log_metadata JSONB NOT NULL DEFAULT '{}',
            received_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            PRIMARY KEY (id, timestamp)
        ) PARTITION BY RANGE (timestamp)
    ''')

    # Create indexes on the parent table (will be inherited by partitions)
    op.execute('CREATE INDEX ix_edge_logs_timestamp ON edge_logs (timestamp)')
    op.execute('CREATE INDEX ix_edge_logs_source_id ON edge_logs (source_id)')
    op.execute('CREATE INDEX ix_edge_logs_level ON edge_logs (level)')

    # Create initial partitions for today and the next 7 days
    # This ensures the table is ready to receive data immediately
    today = datetime.utcnow().date()
    for i in range(8):  # Today + 7 days
        partition_date = today + timedelta(days=i)
        next_date = partition_date + timedelta(days=1)
        partition_name = f"edge_logs_{partition_date.strftime('%Y%m%d')}"

        op.execute(f'''
            CREATE TABLE IF NOT EXISTS {partition_name}
            PARTITION OF edge_logs
            FOR VALUES FROM ('{partition_date.isoformat()}')
            TO ('{next_date.isoformat()}')
        ''')


def downgrade() -> None:
    # Get and drop all partitions first
    # PostgreSQL requires partitions to be dropped before the parent table
    op.execute('''
        DO $$
        DECLARE
            partition_name TEXT;
        BEGIN
            FOR partition_name IN
                SELECT inhrelid::regclass::text
                FROM pg_inherits
                WHERE inhparent = 'edge_logs'::regclass
            LOOP
                EXECUTE 'DROP TABLE IF EXISTS ' || partition_name || ' CASCADE';
            END LOOP;
        END $$
    ''')

    # Drop the parent table
    op.execute('DROP TABLE IF EXISTS edge_logs CASCADE')
