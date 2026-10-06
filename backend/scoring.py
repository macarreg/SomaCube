from sqlalchemy import func
from datetime import datetime
from models import db, Solution, User, HintEvent
from totals import get_shape_total, get_shape_totals


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

def _collect_shape(shape_id):
    """Per-user stats for one figure."""
    total = get_shape_total(shape_id)
    rows = (
        db.session.query(Solution.user_id, func.count(Solution.id),
                         func.max(Solution.discovered_at))
        .filter(Solution.user_id.isnot(None), Solution.shape_id == shape_id)
        .group_by(Solution.user_id)
        .all()
    )
    stats = {
        uid: {"solutions": n, "last_found_at": last,
              "complete": bool(total) and n >= total}
        for uid, n, last in rows
    }
    hints_by_user = dict(
        db.session.query(HintEvent.user_id, func.count(HintEvent.id))
        .filter(HintEvent.user_id.isnot(None), HintEvent.shape_id == shape_id)
        .group_by(HintEvent.user_id)
        .all()
    )
    return stats, hints_by_user, total


def _collect_total():
    """Per-user stats across every figure, including shapes completed."""
    rows = (
        db.session.query(Solution.user_id, Solution.shape_id,
                         func.count(Solution.id), func.max(Solution.discovered_at))
        .filter(Solution.user_id.isnot(None))
        .group_by(Solution.user_id, Solution.shape_id)
        .all()
    )
    totals = get_shape_totals({sid for _, sid, _, _ in rows})
    stats = {}
    for uid, sid, n, last in rows:
        s = stats.setdefault(uid, {"solutions": 0, "last_found_at": None,
                                   "shapes_completed": 0})
        s["solutions"] += n
        if last and (s["last_found_at"] is None or last > s["last_found_at"]):
            s["last_found_at"] = last
        shape_total = totals.get(sid)
        if shape_total and n >= shape_total:
            s["shapes_completed"] += 1
    hints_by_user = dict(db.session.query(User.id, User.hints_used).all())
    return stats, hints_by_user, None


def get_leaderboard(shape_id="total", viewer_id=None, limit=50):
    """Ranked entries for one figure or the overall total, plus the viewer's
    own row. Returns only usernames, never emails or user ids.

    Ranking: most solutions, then fewest hints, then whoever reached their
    current count first."""
    is_total = shape_id == "total"
    stats, hints_by_user, shape_total = _collect_total() if is_total else _collect_shape(shape_id)

    ids = set(stats) | ({viewer_id} if viewer_id is not None else set())
    names = {}
    if ids:
        names = dict(db.session.query(User.id, User.username).filter(User.id.in_(ids)).all())

    def build(uid):
        s = stats.get(uid, {})
        entry = {
            "solutions": s.get("solutions", 0),
            "hints": hints_by_user.get(uid, 0) or 0,
            "last_found_at": s.get("last_found_at") or datetime.max,
        }
        if is_total:
            entry["shapes_completed"] = s.get("shapes_completed", 0)
        else:
            entry["complete"] = s.get("complete", False)
        return entry

    def public(entry, **extra):
        out = {k: v for k, v in entry.items() if k != "last_found_at"}
        out.update(extra)
        return out

    ranked = []
    for uid in stats:
        name = names.get(uid)
        if not name:            # no username yet -> not shown publicly
            continue
        entry = build(uid)
        entry["_uid"], entry["username"] = uid, name
        ranked.append(entry)

    ranked.sort(key=lambda e: (-e["solutions"], e["hints"], e["last_found_at"],
                               e["username"].lower()))
    for i, e in enumerate(ranked, 1):
        e["rank"] = i

    me = None
    if viewer_id is not None:
        my_name = names.get(viewer_id)
        my_rank = next((e["rank"] for e in ranked if e["_uid"] == viewer_id), None)
        me = public(build(viewer_id), username=my_name,
                    has_username=bool(my_name), rank=my_rank)

    return {
        "shape_id": shape_id,
        "scope": "total" if is_total else "shape",
        "total_solutions": shape_total,
        "ranked_players": len(ranked),
        "entries": [
            public({k: v for k, v in e.items() if k != "_uid"},
                   is_me=(e["_uid"] == viewer_id))
            for e in ranked[:limit]
        ],
        "me": me,
    }


def has_user_found_solution(user_id, shape_id, normalized_solution):
    return db.session.query(Solution.id).filter_by(
        user_id=user_id, shape_id=shape_id, normalized_solution=normalized_solution
    ).first() is not None