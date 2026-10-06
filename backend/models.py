# models.py
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(UUID(as_uuid=True), primary_key=True)
    email = db.Column(db.String(320), nullable=False)
    username = db.Column(db.String(20), nullable=True)
    hints_used = db.Column(db.Integer, nullable=False, default=0, server_default='0')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        # Case-insensitive uniqueness ("Bob" and "bob" collide). NULLs are
        # allowed to repeat, so users without a username don't conflict.
        db.Index('uq_users_username_lower', db.func.lower(username), unique=True),
    )


class Solution(db.Model):
    __tablename__ = 'solutions'
    id = db.Column(db.Integer, primary_key=True)
    # UUID to match Supabase Auth's auth.users.id. Still nullable — anonymous
    # rows (pre-auth testing) keep user_id=None; real users get a real UUID.
    user_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)
    shape_id = db.Column(db.String(120), nullable=False, index=True)
    normalized_solution = db.Column(db.Text, nullable=False)
    discovered_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'shape_id', 'normalized_solution',
                             name='uq_user_shape_solution'),
    )


class HintEvent(db.Model):
    __tablename__ = 'hint_events'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)
    shape_id = db.Column(db.String(120), nullable=False, index=True)
    piece_id = db.Column(db.String(10), nullable=True)
    used_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.Index('ix_hint_events_user_shape', 'user_id', 'shape_id'),
    )


class ShapeTotal(db.Model):
    """Cached YASS solution count per figure (the count never changes)."""
    __tablename__ = 'shape_totals'
    shape_id = db.Column(db.String(120), primary_key=True)
    total_solutions = db.Column(db.Integer, nullable=False)
    computed_at = db.Column(db.DateTime, default=datetime.utcnow)