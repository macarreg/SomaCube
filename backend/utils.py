import os
import logging
import json
from typing import Set, Tuple, Optional
import itertools

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Constants
VALID_PIECES = {'3', 'l', 't', 'z', 'p', 'n', 'c', '.'}
VALID_GRID_SPACES = {'*', 'o'}  # Both '*' and 'o' indicate valid grid spaces

# ---------------------------------------------------------------------------
# Rotation-invariant solution normalization
# ---------------------------------------------------------------------------
def _build_rotations():
    """The 24 proper rotation matrices of the cube (no reflections)."""
    rx = ((1, 0, 0), (0, 0, -1), (0, 1, 0))
    ry = ((0, 0, 1), (0, 1, 0), (-1, 0, 0))
    rz = ((0, -1, 0), (1, 0, 0), (0, 0, 1))
    identity = ((1, 0, 0), (0, 1, 0), (0, 0, 1))

    def mul(a, b):
        return tuple(
            tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3))
            for i in range(3)
        )

    seen, frontier = {identity}, [identity]
    while frontier:
        m = frontier.pop()
        for r in (rx, ry, rz):
            n = mul(r, m)
            if n not in seen:
                seen.add(n)
                frontier.append(n)
    return sorted(seen)

_ROTATIONS = _build_rotations()
assert len(_ROTATIONS) == 24


def _canonical_from_cells(cells) -> str:
    """cells: iterable of (x, y, z, piece_char). Returns the lexicographically
    smallest 'z,y,x:piece;...' string over all 24 whole-figure rotations.
    Piece letters move with their cells, so different piece arrangements of
    the same occupied space remain distinct."""
    cells = list(cells)
    best = None
    for m in _ROTATIONS:
        rotated = [
            (
                m[0][0] * x + m[0][1] * y + m[0][2] * z,
                m[1][0] * x + m[1][1] * y + m[1][2] * z,
                m[2][0] * x + m[2][1] * y + m[2][2] * z,
                c,
            )
            for x, y, z, c in cells
        ]
        mx = min(p[0] for p in rotated)
        my = min(p[1] for p in rotated)
        mz = min(p[2] for p in rotated)
        candidate = sorted((z - mz, y - my, x - mx, c) for x, y, z, c in rotated)
        if best is None or candidate < best:
            best = candidate
    return ";".join(f"{z},{y},{x}:{c}" for z, y, x, c in best)


def canonicalize_string(normalized: str) -> str:
    """Re-canonicalize an already-normalized 'z,y,x:piece;...' string
    (e.g. one stored by the old normalizer). Idempotent."""
    cells = []
    for part in normalized.split(';'):
        coords, c = part.split(':')
        z, y, x = map(int, coords.split(','))
        cells.append((x, y, z, c))
    return _canonical_from_cells(cells)


def normalize_solution(solution: str, shape_id: str) -> str:
    """Canonical, rotation-invariant string for a solved grid."""
    try:
        layers = solution.strip().split('\n\n')
        cells = [
            (x, y, z, char)
            for z, layer in enumerate(layers)
            for y, row in enumerate(layer.split('\n'))
            for x, char in enumerate(row)
            if char != '.'
        ]
        if not cells:
            return solution.strip()
        return _canonical_from_cells(cells)
    except Exception as e:
        logger.error(f"Error normalizing solution: {str(e)}")
        return solution.strip()

def load_solutions(shape_id: str) -> Set[str]:
    solutions_file = os.path.join(os.path.dirname(__file__), 'solutions', f"{shape_id}_solutions.json")
    if not os.path.exists(solutions_file):
        return set()

    try:
        with open(solutions_file, 'r') as f:
            raw_entries = json.load(f)

        migrated_solutions = set()
        needs_rewrite = False

        for entry in raw_entries:
            # If an entry is in the legacy multi-line format, normalize it
            if '\n' in entry:
                norm = normalize_solution(entry, shape_id)
            else:
                norm = canonicalize_string(entry)
            if norm != entry:
                needs_rewrite = True
            migrated_solutions.add(norm)

        # Resave if legacy formats were updated
        if needs_rewrite:
            with open(solutions_file, 'w') as f:
                json.dump(list(migrated_solutions), f)

        return migrated_solutions

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
            os.makedirs(os.path.dirname(solutions_file), exist_ok=True)
            with open(solutions_file, 'w') as f:
                json.dump(list(solutions), f)
        
        return True, not is_known, normalized, len(solutions)
    except Exception as e:
        logger.error(f"Error handling solution: {str(e)}")
        return False, False, None, 0 