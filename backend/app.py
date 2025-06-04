from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import logging
import subprocess
from soma_grid import SomaGrid
from utils import handle_solution, load_solutions, normalize_solution, VALID_PIECES

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)

@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

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
def check_solution():
    try:
        data = request.json
        if not data or 'grid_state' not in data or 'shape_id' not in data:
            return jsonify({"error": "Missing grid state or shape ID"}), 400
            
        grid_state = data['grid_state']
        shape_id = data['shape_id']
        
        is_valid, is_new, normalized, solution_count = handle_solution(shape_id, grid_state)
        if not is_valid:
            return jsonify({
                "valid": False,
                "message": "Invalid grid state: pieces must be placed only in allowed cells"
            }), 400

        return jsonify({
            "valid": True,
            "message": "YAY! New solution!" if is_new else "This is a known solution.",
            "solution_count": solution_count
        })
                
    except Exception as e:
        logger.error(f"Error checking solution: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/solutions/<shape_id>')
def get_solutions(shape_id):
    try:
        solutions = load_solutions(shape_id)
        return jsonify(list(solutions))
    except Exception as e:
        logger.error(f"Error getting solutions for {shape_id}: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/total-solutions/<shape_id>')
def get_total_solutions(shape_id):
    try:
        soma_path = os.path.join(os.path.dirname(__file__), 'yass', 'figures', f"{shape_id}.soma")
        soma_executable = os.path.join(os.path.dirname(__file__), 'yass', 'soma')
        
        result = subprocess.run([soma_executable, '-cq', soma_path], 
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

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)