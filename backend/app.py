from dotenv import load_dotenv
load_dotenv()
from flask import Flask, request, jsonify, send_from_directory, g
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os
import logging
import subprocess
from soma_grid import SomaGrid
from utils import handle_solution, load_solutions, normalize_solution, VALID_PIECES
from hint_solver import compute_hint, get_next_hint_piece
from config import Config
from models import db, Solution, User
from scoring import get_user_shape_stats, get_leaderboard, has_user_found_solution, get_user_solution_count
from sqlalchemy.exc import IntegrityError
from auth import load_current_user, require_auth, _decode_token, check_email_exists
from typing import Optional


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)

app.config.from_object(Config)
db.init_app(app)

with app.app_context():
    db.create_all()  # fine for dev; use Alembic migrations once this is live (see below)

limiter = Limiter(
    get_remote_address, app=app, headers_enabled=True,
    storage_uri=os.environ.get("REDIS_URL", "memory://"),
    default_limits=["200 per hour"],
    swallow_errors=True,               # don't 500 if Redis is down
    in_memory_fallback_enabled=True,   # fall back to per-process counting
)

@app.errorhandler(429)
def rate_limited(e):
    return jsonify({"error": "rate_limited",
                    "message": "Too many requests. Please slow down and try again shortly."}), 429

app.before_request(load_current_user)

@app.route('/api/config')
def get_public_config():
    return jsonify({
        "supabaseUrl": Config.SUPABASE_URL,
        "supabaseAnonKey": Config.SUPABASE_ANON_KEY,
    })

@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/node_modules/<path:filename>')
def serve_node_modules(filename):
    return send_from_directory('../node_modules', filename)

@app.route('/api/shapes')
def get_shapes():
    try:
        shapes = SomaGrid.get_available_shapes()
        return jsonify(shapes)
    except Exception as e:
        logger.error(f"Error in get_shapes: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/soma/<filename>')
def get_soma_file(filename):
    try:
        figures_dir = os.path.join(os.path.dirname(__file__), 'yass', 'figures')
        file_path = os.path.join(figures_dir, filename)
        
        if not os.path.exists(file_path):
            return jsonify({"error": f"File {filename} not found"}), 404
            
        grid = SomaGrid.from_soma_file(file_path)
        return jsonify(grid.to_dict())
    except Exception as e:
        logger.error(f"Error loading soma file {filename}: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/check-solution', methods=['POST'])
@limiter.limit("30 per minute")  # rate limit to prevent abuse
def check_solution():
    try:
        data = request.get_json(silent=True) or {}
        grid_state = data.get('grid_state')
        shape_id = data.get('shape_id')
        save_if_new = data.get('save', True)

        if not grid_state or not shape_id:
            return jsonify({"error": "Missing grid state or shape ID"}), 400

        # handle_solution/load_solutions in utils.py are a *global* file-backed
        # registry (used internally by the hint solver to avoid re-offering an
        # already-known tiling to anyone). They are NOT per-user, so `is_new`
        # and the count they return must never be shown to the person as
        # "your" progress. Only `is_valid`/`normalized` are used below;
        # per-user truth comes from the `solutions` DB table via scoring.py.
        is_valid, is_new, normalized, _ = handle_solution(
            shape_id, grid_state, check_only=not save_if_new
        )

        if not is_valid:
            return jsonify({
                "valid": False,
                "message": "Invalid grid state: pieces must be placed only in allowed cells"
            }), 400

        if g.user_id is not None:
            already_found_by_user = has_user_found_solution(g.user_id, shape_id, normalized)
        else:
            # No account to check against the DB, so fall back to the
            # global file-based check for sensible "new"/"known" messaging.
            already_found_by_user = not is_new

        saved = False
        if g.user_id is not None and not already_found_by_user and save_if_new:
            try:
                db.session.add(Solution(
                    user_id=g.user_id,
                    shape_id=shape_id,
                    normalized_solution=normalized,
                ))
                db.session.commit()
                saved = True
            except IntegrityError:
                db.session.rollback()  # double-click race: already saved
                already_found_by_user = True
            except Exception as e:
                db.session.rollback()
                logger.error(f"Failed to record solution: {e}")
                return jsonify({
                    "valid": True,
                    "saved": False,
                    "message": "Valid solution, but we couldn't save it. Please try again."
                }), 500

        solution_count = (get_user_solution_count(g.user_id, shape_id)
                if g.user_id is not None else 0)

        if g.user_id is None:
            message = "Valid solution! Log in to save it to your account."
        elif already_found_by_user:
            message = "You've already found this solution."
        else:
            message = "YAY! New solution saved!"

        return jsonify({
            "valid": True,
            "saved": saved,
            "authenticated": g.user_id is not None,
            "message": message,
            "solution_count": solution_count,
        })

    except Exception as e:
        logger.error(f"Error checking solution: {str(e)}")
        return jsonify({"error": "Something went wrong checking your solution."}), 500
    

@app.route('/api/solutions/<shape_id>', methods=['GET'])
def get_shape_solutions(shape_id):
    if g.user_id is None:
        # Not logged in: no account to tie a count to, always show 0.
        solution_count = 0
    else:
        solution_count = (get_user_solution_count(g.user_id, shape_id)
                  if g.user_id is not None else 0)
    return jsonify({
        "shape_id": shape_id,
        "solution_count": solution_count
    })

def _record_hint() -> Optional[int]:
    """Atomically add 1 to the logged-in user's hint counter.
    Returns the new total, or None for anonymous users, a missing users
    row, or a DB failure."""
    if g.user_id is None:
        return None
    try:
        new_total = db.session.execute(
            db.update(User)
            .where(User.id == g.user_id)
            .values(hints_used=User.hints_used + 1)
            .returning(User.hints_used)
            .execution_options(synchronize_session=False)
        ).scalar_one_or_none()
        db.session.commit()
        return new_total
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to increment hints_used: {e}")
        return None


@app.route('/api/hint', methods=['POST'])
@limiter.limit("10 per minute")  # rate limit to prevent abuse
def get_hint():
    try:
        data = request.get_json(silent=True)
        if not data or 'grid_state' not in data or 'shape_id' not in data:
            return jsonify({"error": "Missing grid state or shape ID"}), 400

        grid_state = data['grid_state']
        shape_id = data['shape_id']
        cached_solution = data.get('cached_solution')

        ignored_pieces = set(data.get('ignored_pieces', []))

        # Fast path: the client already holds a full solution, so just pick
        # the next piece from it. If the board has diverged from that
        # solution (or every piece is placed), get_next_hint_piece returns
        # None and we fall through to computing a fresh one below.
        if cached_solution:
            hint = get_next_hint_piece(grid_state, cached_solution, ignored_pieces)
            if hint is not None:
                hints_used = _record_hint()
                return jsonify({
                    "success": True,
                    "message": f"Hint: place the {hint['piece_id']} piece.",
                    "hint": hint,
                    "full_solution": cached_solution,
                    "from_cache": True,
                    "removed_pieces": [],
                    "tracked": hints_used is not None,
                    "hints_used": hints_used,
                })

        result = compute_hint(grid_state, shape_id)
        hints_used = _record_hint() if result.get("success") else None
        result["tracked"] = hints_used is not None
        result["hints_used"] = hints_used
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error computing hint: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/total-solutions/<shape_id>')
def get_total_solutions(shape_id):
    try:
        soma_path = os.path.join(os.path.dirname(__file__), 'yass', 'figures', f"{shape_id}.soma")
        soma_executable = os.path.join(os.path.dirname(__file__), 'yass', 'soma')
        
        result = subprocess.run([soma_executable, '-acr', soma_path], 
                              capture_output=True, 
                              text=True,
                              cwd=os.path.join(os.path.dirname(__file__), 'yass'))
        
        if result.returncode != 0:
            return jsonify({"error": "Failed to get total solutions"}), 500
            
        total_solutions = int(result.stdout.split()[-2])
        return jsonify({"total_solutions": total_solutions})
            
    except Exception as e:
        logger.error(f"Error getting total solutions for {shape_id}: {str(e)}")
        return jsonify({"error": str(e)}), 500
    
@app.route('/api/stats/<shape_id>')
def get_stats(shape_id):
    if g.user_id is None:
        return jsonify({"solutions_found": 0, "hints_used": 0})
    return jsonify(get_user_shape_stats(g.user_id, shape_id))

@app.route('/api/leaderboard')
def leaderboard():
    shape_id = request.args.get('shape_id')
    rows = get_leaderboard(shape_id=shape_id)
    return jsonify([{"user_id": uid, "solutions_found": total} for uid, total in rows])

@app.route('/api/auth/check-email', methods=['POST'])
@limiter.limit("5 per minute;20 per hour")  # this endpoint answers "does this email exist?" — keep it tight
def check_email():
    data = request.json or {}
    email = (data.get('email') or '').strip().lower()
    if not email:
        return jsonify({"error": "Missing email"}), 400

    exists = check_email_exists(email)
    if exists is None:
        return jsonify({"exists": None, "error": "Could not verify at this time"}), 503
    return jsonify({"exists": exists})


@app.route('/api/whoami')
def whoami():
    """Debug helper — hit this with your access token to see exactly why
    auth is or isn't recognizing you. Never exposes secrets, safe to keep."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"user_id": None, "note": "No Authorization header received"})
    token = auth_header[len("Bearer "):].strip()
    try:
        claims = _decode_token(token)
        return jsonify({"user_id": claims.get("sub"), "email": claims.get("email")})
    except Exception as e:
        return jsonify({"user_id": None, "error": str(e)}), 401

if __name__ == '__main__':
    app.run(
	debug=False,
	host='0.0.0.0',
	port=int(os.environ.get("PORT", 8000))
    )