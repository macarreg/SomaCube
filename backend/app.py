from dotenv import load_dotenv
load_dotenv()
from flask import Flask, request, jsonify, send_from_directory
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
from models import db, Solution, HintEvent
from scoring import get_user_shape_stats, get_leaderboard, has_user_found_solution
from sqlalchemy.exc import IntegrityError

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)

app.config.from_object(Config)
db.init_app(app)

with app.app_context():
    db.create_all()  # fine for dev; use Alembic migrations once this is live (see below)

CURRENT_USER_ID = None  # placeholder until auth exists — swap for e.g. session['user_id']

limiter = Limiter(
    get_remote_address,
    app=app,
    storage_uri=os.environ.get("REDIS_URL", "memory://"),  # falls back to in-memory locally
    default_limits=["200 per hour"],
)

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
        data = request.json or {}
        grid_state = data.get('grid_state')
        shape_id = data.get('shape_id')
        save_if_new = data.get('save', True)

        if not grid_state or not shape_id:
            return jsonify({"error": "Missing grid state or shape ID"}), 400

        is_valid, is_new, normalized, solution_count = handle_solution(
            shape_id, grid_state, check_only=not save_if_new
        )

        if not is_valid:
            return jsonify({
                "valid": False,
                "message": "Invalid grid state: pieces must be placed only in allowed cells"
            }), 400
        
        already_found_by_user = has_user_found_solution(CURRENT_USER_ID, shape_id, normalized)

        if not already_found_by_user:
            try:
                db.session.add(Solution(
                    user_id=CURRENT_USER_ID,
                    shape_id=shape_id,
                    normalized_solution=normalized,
                ))
                db.session.commit()
            except IntegrityError:
                # two rapid clicks raced each other to insert the same row —
                # harmless, the unique constraint just did its job
                db.session.rollback()

        # ← this is the part that writes to Supabase, right when a new solution is found
        if is_new and save_if_new:
            try:
                db.session.add(Solution(
                    user_id=CURRENT_USER_ID,
                    shape_id=shape_id,
                    normalized_solution=normalized,
                ))
                db.session.commit()
            except Exception as e:
                db.session.rollback()  # don't let a DB hiccup break the response
                logger.error(f"Failed to record solution: {e}")

        return jsonify({
            "valid": True,
            "message": "YAY! New solution!" if is_new else "This is a known solution.",
            "solution_count": solution_count
        })

    except Exception as e:
        logger.error(f"Error checking solution: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/solutions/<shape_id>', methods=['GET'])
def get_shape_solutions(shape_id):
    solutions = load_solutions(shape_id)
    return jsonify({
        "shape_id": shape_id,
        "solution_count": len(solutions)
    })

@app.route('/api/hint', methods=['POST'])
@limiter.limit("10 per minute")  # rate limit to prevent abuse
def get_hint():
    try:
        data = request.json
        if not data or 'grid_state' not in data or 'shape_id' not in data:
            return jsonify({"error": "Missing grid state or shape ID"}), 400

        grid_state = data['grid_state']
        shape_id = data['shape_id']
        cached_solution = data.get('cached_solution')

        ignored_pieces = set(data.get('ignored_pieces', []))

        if cached_solution:
            hint = get_next_hint_piece(grid_state, cached_solution, ignored_pieces)
            if hint is not None:
                return jsonify({
                    "success": True,
                    "message": f"Hint: place the {hint['piece_id']} piece.",
                    "hint": hint,
                    "full_solution": cached_solution,
                    "from_cache": True,
                })

        result = compute_hint(grid_state, shape_id)
        if result.get("success"):
            try:
                db.session.add(HintEvent(
                    user_id=CURRENT_USER_ID,
                    shape_id=shape_id,
                    piece_id=result["hint"]["piece_id"],
                ))
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                logger.error(f"Failed to record hint event: {e}")

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
    return jsonify(get_user_shape_stats(CURRENT_USER_ID, shape_id))

@app.route('/api/leaderboard')
def leaderboard():
    shape_id = request.args.get('shape_id')
    rows = get_leaderboard(shape_id=shape_id)
    return jsonify([{"user_id": uid, "solutions_found": total} for uid, total in rows])

if __name__ == '__main__':
    app.run(
	debug=False,
	host='0.0.0.0',
	port=int(os.environ.get("PORT", 8000))
    )
