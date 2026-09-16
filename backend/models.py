from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    solutions = db.relationship('Solution', back_populates='user', lazy='dynamic')
    hints = db.relationship('HintEvent', back_populates='user', lazy='dynamic')


class Solution(db.Model):
    """One row per unique solution a user has discovered for a shape."""
    __tablename__ = 'solutions'
    id = db.Column(db.Integer, primary_key=True)
    # Placeholder: nullable until auth exists. Pre-auth / anonymous solutions
    # get user_id=None; nothing here changes shape once login is added.
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    shape_id = db.Column(db.String(120), nullable=False, index=True)
    normalized_solution = db.Column(db.Text, nullable=False)
    discovered_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', back_populates='solutions')

    __table_args__ = (
        # A given normalized solution should only be "discovered" once per
        # user per shape — prevents duplicate rows if check-solution is
        # called twice for the same board.
        db.UniqueConstraint('user_id', 'shape_id', 'normalized_solution',
                             name='uq_user_shape_solution'),
    )


class HintEvent(db.Model):
    """One row per hint actually served to a user."""
    __tablename__ = 'hint_events'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    shape_id = db.Column(db.String(120), nullable=False, index=True)
    piece_id = db.Column(db.String(10), nullable=True)
    used_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', back_populates='hints')