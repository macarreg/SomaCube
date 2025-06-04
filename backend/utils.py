import os
import logging
import json
from typing import Set, Tuple, Optional

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Constants
VALID_PIECES = {'3', 'l', 't', 'z', 'p', 'n', 'c', '.'}
VALID_GRID_SPACES = {'*', 'o'}  # Both '*' and 'o' indicate valid grid spaces

def load_solutions(shape_id: str) -> Set[str]:
    """Load known solutions from the shape-specific solutions file."""
    solutions_dir = os.path.join(os.path.dirname(__file__), 'solutions')
    os.makedirs(solutions_dir, exist_ok=True)
    solutions_file = os.path.join(solutions_dir, f"{shape_id}_solutions.json")
    
    try:
        if not os.path.exists(solutions_file):
            return set()
        with open(solutions_file, 'r') as f:
            solutions = json.load(f)
            return set(solutions)
    except Exception as e:
        logger.error(f"Error loading solutions for {shape_id}: {str(e)}")
        return set()

def is_valid_placement(grid_state: str, shape_id: str) -> bool:
    """Check if the grid state is valid by comparing against the original shape file."""
    try:
        # Load the original shape file
        figures_dir = os.path.join(os.path.dirname(__file__), 'yass', 'figures')
        shape_file = os.path.join(figures_dir, f"{shape_id}.soma")
        
        if not os.path.exists(shape_file):
            logger.error(f"Shape file not found: {shape_file}")
            return False
            
        with open(shape_file, 'r') as f:
            original_shape = f.read().strip()
            
        # Split both into layers
        original_layers = original_shape.split('\n\n')
        grid_layers = grid_state.strip().split('\n\n')
        
        # Check layer count
        if len(original_layers) != len(grid_layers):
            logger.error(f"Layer count mismatch: original={len(original_layers)}, grid={len(grid_layers)}")
            return False
            
        # Compare each layer
        for i, (original_layer, grid_layer) in enumerate(zip(original_layers, grid_layers)):
            original_rows = original_layer.strip().split('\n')
            grid_rows = grid_layer.strip().split('\n')
            
            # Check row count
            if len(original_rows) != len(grid_rows):
                logger.error(f"Row count mismatch in layer {i}: original={len(original_rows)}, grid={len(grid_rows)}")
                return False
                
            # Compare each row
            for j, (original_row, grid_row) in enumerate(zip(original_rows, grid_rows)):
                # Check row length
                if len(original_row) != len(grid_row):
                    logger.error(f"Row length mismatch in layer {i}, row {j}: original={len(original_row)}, grid={len(grid_row)}")
                    return False
                    
                # Compare each cell
                for k, (original_cell, grid_cell) in enumerate(zip(original_row, grid_row)):
                    # If original cell is '.', grid cell must also be '.'
                    if original_cell == '.' and grid_cell != '.':
                        logger.error(f"Invalid piece placement at layer {i}, row {j}, col {k}: original='.', grid='{grid_cell}'")
                        return False
                    # If original cell is '*' or 'o', grid cell must be either '.' or a valid piece
                    elif original_cell in VALID_GRID_SPACES and grid_cell not in VALID_PIECES:
                        logger.error(f"Invalid piece at layer {i}, row {j}, col {k}: original='{original_cell}', grid='{grid_cell}'")
                        return False
                    # If grid cell is a piece, original cell must be '*' or 'o'
                    elif grid_cell in VALID_PIECES and grid_cell != '.' and original_cell not in VALID_GRID_SPACES:
                        logger.error(f"Piece placed in invalid position at layer {i}, row {j}, col {k}: original='{original_cell}', grid='{grid_cell}'")
                        return False
        
        return True
        
    except Exception as e:
        logger.error(f"Error validating grid state: {str(e)}")
        return False

def normalize_solution(solution: str, shape_id: str) -> str:
    """Normalize a solution by rotating it to a canonical form."""
    try:
        figures_dir = os.path.join(os.path.dirname(__file__), 'yass', 'figures')
        shape_file = os.path.join(figures_dir, f"{shape_id}.soma")
        
        if not os.path.exists(shape_file):
            logger.error(f"Shape file not found: {shape_file}")
            return solution.strip()
            
        with open(shape_file, 'r') as f:
            original_shape = f.read().strip()
            
        original_layers = original_shape.split('\n\n')
        original_height = len(original_layers[0].split('\n'))
        original_width = len(original_layers[0].split('\n')[0])
        original_depth = len(original_layers)
        
        # Convert solution to 3D array
        layers = solution.strip().split('\n\n')
        grid = [[list(row) for row in layer.split('\n')] for layer in layers]
        height = len(grid[0])
        width = len(grid[0][0])
        depth = len(grid)
        
        def get_piece_positions(grid):
            """Get the positions of all pieces in the grid."""
            positions = []
            for z in range(depth):
                for y in range(height):
                    for x in range(width):
                        if grid[z][y][x] != '.':
                            positions.append((x, y, z, grid[z][y][x]))
            return positions
        
        def rotate_positions(positions, axis):
            """Rotate piece positions around the given axis."""
            rotated = []
            for x, y, z, piece in positions:
                if axis == 'x':
                    new_x, new_y, new_z = x, -z, y
                elif axis == 'y':
                    new_x, new_y, new_z = z, y, -x
                else:  # z
                    new_x, new_y, new_z = -y, x, z
                rotated.append((new_x, new_y, new_z, piece))
            return rotated
        
        def positions_to_grid(positions):
            """Convert piece positions back to a grid."""
            grid = [[['.' for _ in range(width)] for _ in range(height)] for _ in range(depth)]
            
            # Find the minimum coordinates to normalize position
            min_x = min(x for x, _, _, _ in positions)
            min_y = min(y for _, y, _, _ in positions)
            min_z = min(z for _, _, z, _ in positions)
            
            # Place pieces in grid, normalized to start at (0,0,0)
            for x, y, z, piece in positions:
                norm_x = x - min_x
                norm_y = y - min_y
                norm_z = z - min_z
                if 0 <= norm_x < width and 0 <= norm_y < height and 0 <= norm_z < depth:
                    grid[norm_z][norm_y][norm_x] = piece
            
            return grid
        
        def grid_to_string(grid):
            """Convert grid to string format."""
            layers = []
            for layer in grid:
                rows = [''.join(row) for row in layer]
                layers.append('\n'.join(rows))
            return '\n\n'.join(layers)
        
        positions = get_piece_positions(grid)
        rotations = set()
        
        # Try all possible rotations (4 for each axis)
        for _ in range(4):  # Z rotations
            for _ in range(4):  # Y rotations
                for _ in range(4):  # X rotations
                    rotated_grid = positions_to_grid(positions)
                    rotated_str = grid_to_string(rotated_grid)
                    if is_valid_placement(rotated_str, shape_id):
                        rotations.add(rotated_str)
                    positions = rotate_positions(positions, 'x')
                positions = rotate_positions(positions, 'y')
            positions = rotate_positions(positions, 'z')
        
        if not rotations:
            logger.error("No valid rotations found for the shape")
            return solution.strip()
            
        min_solution = min(rotations)
        logger.debug(f"Found {len(rotations)} unique rotations")
        return min_solution
        
    except Exception as e:
        logger.error(f"Error normalizing solution: {str(e)}")
        return solution.strip()

def handle_solution(shape_id: str, solution: str, check_only: bool = False) -> Tuple[bool, bool, Optional[str], int]:
    """Handle a solution: validate, normalize, and optionally save it.
    Returns (is_valid, is_new, normalized_solution, solution_count)"""
    try:
        if not is_valid_placement(solution, shape_id):
            logger.error(f"Invalid placement for shape {shape_id}")
            return False, False, None, 0

        normalized = normalize_solution(solution, shape_id)
        solutions = load_solutions(shape_id)
        is_known = normalized in solutions
        
        if not is_known and not check_only:
            solutions.add(normalized)
            solutions_file = os.path.join(os.path.dirname(__file__), 'solutions', f"{shape_id}_solutions.json")
            with open(solutions_file, 'w') as f:
                json.dump(list(solutions), f)
        
        return True, not is_known, normalized, len(solutions)
    except Exception as e:
        logger.error(f"Error handling solution: {str(e)}")
        return False, False, None, 0 