from sqlalchemy import func
from models import db, Solution, HintEvent


def get_user_shape_stats(user_id, shape_id):
    return {
        "solutions_found": Solution.query.filter_by(
            user_id=user_id, shape_id=shape_id).count(),
        "hints_used": HintEvent.query.filter_by(
            user_id=user_id, shape_id=shape_id).count(),
    }


def get_leaderboard(shape_id=None, limit=10):
    """Top users by solutions found, optionally scoped to one shape."""
    query = (
        db.session.query(Solution.user_id, func.count(Solution.id).label('total'))
        .group_by(Solution.user_id)
    )
    if shape_id:
        query = query.filter(Solution.shape_id == shape_id)
    return query.order_by(func.count(Solution.id).desc()).limit(limit).all()


def has_user_found_solution(user_id, shape_id, normalized_solution):
    return db.session.query(Solution.id).filter_by(
        user_id=user_id, shape_id=shape_id, normalized_solution=normalized_solution
    ).first() is not None