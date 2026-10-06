import logging
import os
import re
import subprocess

from sqlalchemy.exc import IntegrityError

from models import db, ShapeTotal

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(__file__)
FIGURES_DIR = os.path.join(BASE_DIR, 'yass', 'figures')
SOMA_EXE = os.path.join(BASE_DIR, 'yass', 'soma')

_SHAPE_RE = re.compile(r'[A-Za-z0-9_+\-]+')
_cache = {}   # per-process; the DB table is the durable copy


def is_known_shape(shape_id):
    return (isinstance(shape_id, str)
            and bool(_SHAPE_RE.fullmatch(shape_id))
            and os.path.isfile(os.path.join(FIGURES_DIR, f"{shape_id}.soma")))


def available_shape_ids():
    return sorted(f[:-5] for f in os.listdir(FIGURES_DIR) if f.endswith('.soma'))


def _run_yass_count(shape_id):
    result = subprocess.run(
        [SOMA_EXE, '-acr', os.path.join(FIGURES_DIR, f"{shape_id}.soma")],
        capture_output=True, text=True,
        cwd=os.path.join(BASE_DIR, 'yass'),
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"soma exited with {result.returncode}")
    return int(result.stdout.split()[-2])


def get_shape_total(shape_id, compute=True):
    """Total solutions for a figure, or None if unknown/unavailable."""
    if shape_id in _cache:
        return _cache[shape_id]

    row = db.session.get(ShapeTotal, shape_id)
    if row is not None:
        _cache[shape_id] = row.total_solutions
        return row.total_solutions

    if not compute or not is_known_shape(shape_id):
        return None

    try:
        total = _run_yass_count(shape_id)
    except Exception as e:
        logger.error(f"Could not compute total for {shape_id}: {e}")
        return None

    try:
        db.session.add(ShapeTotal(shape_id=shape_id, total_solutions=total))
        db.session.commit()
    except IntegrityError:
        db.session.rollback()   # another worker saved it first
    except Exception as e:
        db.session.rollback()
        logger.error(f"Could not cache total for {shape_id}: {e}")

    _cache[shape_id] = total
    return total


def get_shape_totals(shape_ids, compute=True):
    return {sid: get_shape_total(sid, compute) for sid in shape_ids}