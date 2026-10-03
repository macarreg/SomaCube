from sqlalchemy import func
from models import db, Solution, User


def get_user_hints_used(user_id) -> int:
    return db.session.query(User.hints_used).filter(User.id == user_id).scalar() or 0


def get_user_shape_stats(user_id, shape_id):
    return {
        "solutions_found": Solution.query.filter_by(
            user_id=user_id, shape_id=shape_id).count(),
        "hints_used": get_user_hints_used(user_id),   # total across all puzzles
    }

def get_user_solution_count(user_id, shape_id) -> int:
    return Solution.query.filter_by(user_id=user_id, shape_id=shape_id).count()

def get_leaderboard(shape_id=None, limit=10):
    """Top users by solutions found, optionally scoped to one shape."""
    query = (
        db.session.query(Solution.user_id, func.count(Solution.id).label('total'))
        .filter(Solution.user_id.isnot(None))
        .group_by(Solution.user_id)
    )
    if shape_id:
        query = query.filter(Solution.shape_id == shape_id)
    return query.order_by(func.count(Solution.id).desc()).limit(limit).all()


def has_user_found_solution(user_id, shape_id, normalized_solution):
    return db.session.query(Solution.id).filter_by(
        user_id=user_id, shape_id=shape_id, normalized_solution=normalized_solution
    ).first() is not None