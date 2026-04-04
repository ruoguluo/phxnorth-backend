"""Initial schema with all tables.

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-04-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all tables for PhxNorth backend."""
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_superuser', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=False)

    # Create career_profiles table
    op.create_table(
        'career_profiles',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source', sa.String(length=20), nullable=False),
        sa.Column('raw_text', sa.Text(), nullable=True),
        sa.Column('raw_file_s3_key', sa.String(length=500), nullable=True),
        sa.Column('parsed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('parser_version', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create job_entries table
    op.create_table(
        'job_entries',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('career_profile_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('company_name', sa.String(length=255), nullable=True),
        sa.Column('job_title', sa.String(length=255), nullable=True),
        sa.Column('industry', sa.String(length=100), nullable=True),
        sa.Column('functional_area', sa.String(length=100), nullable=True),
        sa.Column('seniority_level', sa.String(length=50), nullable=True),
        sa.Column('employment_type', sa.String(length=50), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('duration_months', sa.Integer(), nullable=True),
        sa.Column('description_raw', sa.Text(), nullable=True),
        sa.Column('sequence_index', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['career_profile_id'], ['career_profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create career_analytics table
    op.create_table(
        'career_analytics',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('total_roles', sa.Integer(), nullable=True),
        sa.Column('short_tenure_count', sa.Integer(), nullable=True),
        sa.Column('short_tenure_rate', sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column('avg_tenure_months', sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column('career_span_years', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('transition_frequency', sa.Numeric(precision=6, scale=4), nullable=True),
        sa.Column('cross_industry_transitions', sa.Integer(), nullable=True),
        sa.Column('upward_moves', sa.Integer(), nullable=True),
        sa.Column('lateral_moves', sa.Integer(), nullable=True),
        sa.Column('downward_moves', sa.Integer(), nullable=True),
        sa.Column('industry_diversity_score', sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column('functional_diversity_score', sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column('longest_tenure_months', sa.Integer(), nullable=True),
        sa.Column('career_volatility_score', sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column('computed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )

    # Create career_turning_points table
    op.create_table(
        'career_turning_points',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('job_entry_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('point_type', sa.String(length=50), nullable=False),
        sa.Column('inferred_motive', sa.String(length=100), nullable=True),
        sa.Column('context_text', sa.Text(), nullable=True),
        sa.Column('confidence', sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['job_entry_id'], ['job_entries.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create behavioral_events table (TimescaleDB hypertable)
    op.create_table(
        'behavioral_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('event_type', sa.String(length=60), nullable=False),
        sa.Column('payload', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('client_type', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    # Convert to hypertable
    op.execute("SELECT create_hypertable('behavioral_events', 'created_at', chunk_time_interval => INTERVAL '7 days')")
    # Create indexes
    op.create_index('idx_be_user_type', 'behavioral_events', ['user_id', 'event_type', 'created_at'], unique=False)
    op.create_index('idx_be_payload', 'behavioral_events', ['payload'], unique=False, postgresql_using='gin')

    # Create behavioral_metrics table
    op.create_table(
        'behavioral_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('metric_type', sa.String(length=80), nullable=False),
        sa.Column('metric_value', sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column('window_days', sa.Integer(), nullable=False),
        sa.Column('sample_count', sa.Integer(), nullable=True),
        sa.Column('computed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'metric_type', 'window_days', name='uq_behavioral_metrics_user_metric_window')
    )

    # Create disc_profiles table
    op.create_table(
        'disc_profiles',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('d_score', sa.Numeric(precision=5, scale=1), nullable=False),
        sa.Column('i_score', sa.Numeric(precision=5, scale=1), nullable=False),
        sa.Column('s_score', sa.Numeric(precision=5, scale=1), nullable=False),
        sa.Column('c_score', sa.Numeric(precision=5, scale=1), nullable=False),
        sa.Column('dominant', sa.String(length=1), nullable=True),
        sa.Column('secondary', sa.String(length=1), nullable=True),
        sa.Column('confidence', sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column('signal_count', sa.Integer(), nullable=True),
        sa.Column('contradiction_score', sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column('shift_magnitude', sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column('shift_type', sa.String(length=30), nullable=True),
        sa.Column('model_version', sa.String(length=20), nullable=False, server_default='1.0'),
        sa.Column('window_days', sa.Integer(), nullable=True),
        sa.Column('computed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_disc_user_window', 'disc_profiles', ['user_id', 'window_days', 'computed_at'], unique=False)

    # Create preference_profiles table
    op.create_table(
        'preference_profiles',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('stability_vs_growth', sa.Numeric(precision=5, scale=3), nullable=True),
        sa.Column('conservative_vs_aggressive_risk', sa.Numeric(precision=5, scale=3), nullable=True),
        sa.Column('control_vs_collaboration', sa.Numeric(precision=5, scale=3), nullable=True),
        sa.Column('short_term_vs_long_term', sa.Numeric(precision=5, scale=3), nullable=True),
        sa.Column('consistency_score', sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column('computed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create risk_assessments table
    op.create_table(
        'risk_assessments',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('score', sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column('severity', sa.String(length=10), nullable=False),
        sa.Column('evidence', postgresql.JSONB(), nullable=True),
        sa.Column('is_flagged', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('computed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_risk_user_flagged', 'risk_assessments', ['user_id', 'is_flagged', 'computed_at'], unique=False)

    # Create red_flag_events table
    op.create_table(
        'red_flag_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('flag_type', sa.String(length=80), nullable=False),
        sa.Column('severity', sa.String(length=10), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
        sa.Column('resolved', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table('red_flag_events')
    op.drop_table('risk_assessments')
    op.drop_table('preference_profiles')
    op.drop_table('disc_profiles')
    op.drop_table('behavioral_metrics')
    op.drop_table('behavioral_events')
    op.drop_table('career_turning_points')
    op.drop_table('career_analytics')
    op.drop_table('job_entries')
    op.drop_table('career_profiles')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')
