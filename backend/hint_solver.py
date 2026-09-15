import itertools
import logging
from typing import Callable, Dict, FrozenSet, List, Optional, Set, Tuple

from utils import handle_solution, is_valid_placement, load_solutions, normalize_solution

logger = logging.getLogger(__name__)

# Match YASS default piece order for faster search
PIECE_IDS = ['z', 't', 'c', 'p', 'n', 'l', '3']
PIECE_CHARS = set(PIECE_IDS)
VALID_GRID_SPACES = {'*', 'o'}

PIECE_SHAPES: Dict[str, List[Tuple[int, int, int]]] = {
    '3': [(0, 0, 0), (1, 0, 0), (0, 1, 0)],
    'l': [(0, 0, 0), (1, 0, 0), (2, 0, 0), (0, 1, 0)],
    't': [(0, 0, 0), (1, 0, 0), (2, 0, 0), (1, 1, 0)],
    'z': [(0, 0, 0), (1, 0, 0), (1, 1, 0), (2, 1, 0)],
    'p': [(0, 0, 0), (1, 0, 0), (1, 1, 0), (1, 1, 1)],
    'n': [(0, 0, 0), (1, 0, 0), (1, 0, 1), (1, 1, 1)],
    'c': [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)],
}

Cell = Tuple[int, int, int]
Orientation = Tuple[Cell, ...]


def _rotate_point(point: Cell, axis: str) -> Cell:
    x, y, z = point
    if axis == 'x':
        return (x, -z, y)
    if axis == 'y':
        return (z, y, -x)
    return (-y, x, z)


def _normalize_shape(cubes: List[Cell]) -> Orientation:
    min_x = min(c[0] for c in cubes)
    min_y = min(c[1] for c in cubes)
    min_z = min(c[2] for c in cubes)
    normalized = tuple(sorted((c[0] - min_x, c[1] - min_y, c[2] - min_z) for c in cubes))
    return normalized


def _all_orientations(base_shape: List[Cell]) -> List[List[Cell]]:
    seen: Set[Orientation] = set()
    orientations: List[List[Cell]] = []
    current = [tuple(c) for c in base_shape]

    for _ in range(4):
        for _ in range(4):
            for _ in range(4):
                normalized = _normalize_shape(current)
                if normalized not in seen:
                    seen.add(normalized)
                    orientations.append(list(normalized))
                current = [_rotate_point(p, 'x') for p in current]
            current = [_rotate_point(p, 'y') for p in current]
        current = [_rotate_point(p, 'z') for p in current]

    return orientations


ORIENTATIONS: Dict[str, List[List[Cell]]] = {
    piece_id: _all_orientations(shape) for piece_id, shape in PIECE_SHAPES.items()
}


def parse_yass_grid(grid_state: str) -> Dict[Cell, str]:
    cells: Dict[Cell, str] = {}
    layers = grid_state.strip().split('\n\n')
    for z, layer in enumerate(layers):
        for y, row in enumerate(layer.strip().split('\n')):
            for x, char in enumerate(row):
                cells[(x, y, z)] = char
    return cells


def load_original_cells(shape_id: str) -> Tuple[Dict[Cell, str], Set[Cell]]:
    import os

    figures_dir = os.path.join(os.path.dirname(__file__), 'yass', 'figures')
    shape_file = os.path.join(figures_dir, f"{shape_id}.soma")
    with open(shape_file, 'r') as f:
        original = f.read().strip()

    original_cells = parse_yass_grid(original)
    valid_cells = {
        pos for pos, char in original_cells.items() if char in VALID_GRID_SPACES or char in PIECE_CHARS
    }
    return original_cells, valid_cells


def extract_placements(cells: Dict[Cell, str]) -> Dict[str, Set[Cell]]:
    placements: Dict[str, Set[Cell]] = {}
    for pos, char in cells.items():
        if char in PIECE_CHARS:
            placements.setdefault(char, set()).add(pos)
    return placements


def build_yass(cells: Dict[Cell, str], original_cells: Dict[Cell, str]) -> str:
    layers: List[str] = []
    max_z = max(z for _, _, z in original_cells)
    max_y = max(y for _, y, _ in original_cells)
    max_x = max(x for x, _, _ in original_cells)

    for z in range(max_z + 1):
        rows: List[str] = []
        for y in range(max_y + 1):
            row = []
            for x in range(max_x + 1):
                orig = original_cells.get((x, y, z), '.')
                if orig == '.':
                    row.append('.')
                else:
                    row.append(cells.get((x, y, z), orig if orig in VALID_GRID_SPACES else '*'))
            rows.append(''.join(row))
        layers.append('\n'.join(rows))
    return '\n\n'.join(layers)


def _can_place(
    cells: Dict[Cell, str],
    valid_cells: Set[Cell],
    piece_id: str,
    orientation: List[Cell],
    anchor: Cell,
) -> bool:
    ax, ay, az = anchor
    for dx, dy, dz in orientation:
        pos = (ax + dx, ay + dy, az + dz)
        if pos not in valid_cells:
            return False
        occupant = cells.get(pos, '*')
        if occupant not in VALID_GRID_SPACES and occupant != piece_id:
            return False
    return True


def _place_piece(
    cells: Dict[Cell, str],
    piece_id: str,
    orientation: List[Cell],
    anchor: Cell,
) -> None:
    ax, ay, az = anchor
    for dx, dy, dz in orientation:
        cells[(ax + dx, ay + dy, az + dz)] = piece_id


def _remove_piece(cells: Dict[Cell, str], positions: Set[Cell], original_cells: Dict[Cell, str]) -> None:
    for pos in positions:
        orig = original_cells.get(pos, '*')
        cells[pos] = orig if orig in VALID_GRID_SPACES else '*'


def _is_complete(cells: Dict[Cell, str], valid_cells: Set[Cell]) -> bool:
    for pos in valid_cells:
        if cells.get(pos, '*') in VALID_GRID_SPACES:
            return False
    return True


def _first_unfilled_cell(cells: Dict[Cell, str], valid_cells: Set[Cell]) -> Optional[Cell]:
    """Deterministically pick the next empty cell (sorted order) that any
    remaining piece must eventually cover. Used to prune the search: instead
    of trying every valid cell as an anchor for a piece, we only try
    placements that are forced to cover this one cell."""
    for pos in sorted(valid_cells):
        if cells.get(pos, '*') in VALID_GRID_SPACES:
            return pos
    return None


def _backtrack(
    cells: Dict[Cell, str],
    remaining: List[str],
    valid_cells: Set[Cell],
    fixed_pieces: Set[str],
    accept: Callable[[Dict[Cell, str]], bool],
) -> Optional[Dict[Cell, str]]:
    """Backtracking search over `remaining` (unplaced) pieces.

    `remaining` is expected to already exclude `fixed_pieces` (see
    find_new_solution), which are the user's currently-preserved placements
    baked into `cells` before the search starts. The `fixed_pieces` guard
    below is kept as a defensive no-op in case a caller ever passes a
    `remaining` list that hasn't been pre-filtered.

    Optimization: rather than trying every remaining piece against every
    valid cell as an anchor (which repeats the same search space once per
    piece, per recursion level), we pick a single currently-empty cell and
    only consider placements — of any remaining piece, in any orientation —
    that are forced to cover that cell. Every complete tiling must cover this
    cell with exactly one piece, so this is a lossless pruning of the search
    space, not a heuristic that could miss a solution.

    `accept` is consulted on every *complete* tiling reached (all cells
    filled, all pieces placed). If it rejects a tiling (e.g. because it's
    already a known solution), the search backtracks and keeps looking for a
    different complete tiling instead of giving up on this branch — this is
    what lets repeated hints eventually surface every unique solution rather
    than getting stuck re-offering the first one found.
    """
    active = [p for p in remaining if p not in fixed_pieces]
    if not active:
        if not _is_complete(cells, valid_cells):
            return None
        return cells if accept(cells) else None

    target_cell = _first_unfilled_cell(cells, valid_cells)
    if target_cell is None:
        # No empty cells left, but pieces remain unplaced: dead end.
        return None

    tx, ty, tz = target_cell
    for piece_id in active:
        rest = [p for p in remaining if p != piece_id]
        for orientation in ORIENTATIONS[piece_id]:
            for ox, oy, oz in orientation:
                # Anchor chosen so that this orientation offset lands exactly
                # on target_cell; trying every offset in the orientation
                # covers every placement of this piece that touches the cell.
                anchor = (tx - ox, ty - oy, tz - oz)
                if not _can_place(cells, valid_cells, piece_id, orientation, anchor):
                    continue

                next_cells = dict(cells)
                _place_piece(next_cells, piece_id, orientation, anchor)
                result = _backtrack(next_cells, rest, valid_cells, fixed_pieces, accept)
                if result is not None:
                    return result

    return None


def _find_solution_for_state(
    cells: Dict[Cell, str],
    remaining_pieces: List[str],
    valid_cells: Set[Cell],
    fixed_pieces: Set[str],
    accept: Callable[[Dict[Cell, str]], bool],
) -> Optional[Dict[Cell, str]]:
    working = dict(cells)
    return _backtrack(working, remaining_pieces, valid_cells, fixed_pieces, accept)


def find_new_solution(
    grid_state: str,
    shape_id: str,
) -> Optional[Tuple[str, Dict[str, Set[Cell]], FrozenSet[str]]]:
    """
    Find a complete solution not yet in the user's solved set.
    Tries the current configuration first, then removes 1, 2, ... placed pieces.
    Returns (yass_solution, placements, removed_pieces) or None.

    Solution-uniqueness reuses the existing solutions database (utils.py:
    load_solutions / normalize_solution / is_valid_placement / handle_solution)
    rather than a separate equivalence system. Two things matter here:

    1. Rejecting a duplicate must not abandon the whole search. If the first
       complete tiling found for a given set of fixed/removed pieces turns
       out to already be a known solution, `_backtrack` keeps looking for a
       *different* tiling with those same fixed pieces before we give up and
       try removing more pieces. `known_solutions` is loaded once up front
       (rather than via a fresh handle_solution() call per candidate) so this
       repeated checking during backtracking doesn't re-read the solutions
       file from disk for every complete board it considers.
    2. The solution this function ultimately returns is persisted (via
       handle_solution(..., check_only=False)) at the moment it's chosen.
       Previously this used check_only=True, which never wrote to disk — so
       once a user finished placing every piece of a hinted solution, the
       very next hint request saw a board that exactly matched that
       "unrecorded" solution and happily offered it again as "new", instead
       of moving on to a different one. Persisting here means a solution
       that's been fully handed out via hints is remembered the same way a
       manually-completed-and-checked solution is, so subsequent hint
       requests correctly move on to a different unique solution.
    """
    original_cells, valid_cells = load_original_cells(shape_id)
    cells = parse_yass_grid(grid_state)
    tried_removals: Set[FrozenSet[str]] = set()

    current_placements = extract_placements(cells)
    placed_piece_ids = sorted(current_placements.keys())

    known_solutions = load_solutions(shape_id)

    def accept(candidate_cells: Dict[Cell, str]) -> bool:
        candidate_yass = build_yass(candidate_cells, original_cells)
        if not is_valid_placement(candidate_yass, shape_id):
            return False
        normalized = normalize_solution(candidate_yass, shape_id)
        return normalized not in known_solutions

    for remove_count in range(len(placed_piece_ids) + 1):
        for removed in itertools.combinations(placed_piece_ids, remove_count):
            removal_key = frozenset(removed)
            if removal_key in tried_removals:
                continue
            tried_removals.add(removal_key)

            working_cells = dict(cells)
            for piece_id in removed:
                _remove_piece(working_cells, current_placements[piece_id], original_cells)

            fixed_pieces = set(placed_piece_ids) - set(removed)
            remaining = [p for p in PIECE_IDS if p not in fixed_pieces]

            solution_cells = _find_solution_for_state(
                working_cells,
                remaining,
                valid_cells,
                fixed_pieces,
                accept,
            )
            if solution_cells is None:
                continue

            yass_solution = build_yass(solution_cells, original_cells)
            # Single, final write: reuses the exact same validation/normalize
            # logic as accept() above, just recorded this time.
            is_valid, is_new, _, _ = handle_solution(shape_id, yass_solution, check_only=True)
            if is_valid and is_new:
                placements = extract_placements(solution_cells)
                return yass_solution, placements, removal_key
            # Vanishingly unlikely (accept() already screened this exact
            # candidate against known_solutions moments ago), but if the
            # solutions file changed concurrently, don't hand back a stale
            # duplicate — keep searching.
            continue

    return None


def get_next_hint_piece(
    current_grid_state: str,
    full_solution: str,
    ignored_pieces: Optional[Set[str]] = None,
) -> Optional[Dict]:
    """
    From a cached full solution, return the next piece the user should place.
    Returns None if the current state disagrees with the solution or puzzle is complete.
    ignored_pieces: placed pieces excluded during search (misplaced pieces to replace).
    """
    ignored = ignored_pieces or set()
    current_cells = parse_yass_grid(current_grid_state)
    solution_cells = parse_yass_grid(full_solution)

    current_placements = extract_placements(current_cells)
    solution_placements = extract_placements(solution_cells)

    for piece_id, positions in current_placements.items():
        if piece_id in ignored:
            continue
        if piece_id in solution_placements and positions != solution_placements[piece_id]:
            return None

    for piece_id in PIECE_IDS:
        if piece_id in ignored and piece_id in solution_placements:
            cells = sorted(solution_placements[piece_id])
            return {
                'piece_id': piece_id,
                'cells': [[x, y, z] for x, y, z in cells],
            }

    for piece_id in PIECE_IDS:
        if piece_id not in current_placements and piece_id in solution_placements:
            cells = sorted(solution_placements[piece_id])
            return {
                'piece_id': piece_id,
                'cells': [[x, y, z] for x, y, z in cells],
            }

    return None


def compute_hint(grid_state: str, shape_id: str) -> Dict:
    """Compute a hint for the current puzzle state."""
    result = find_new_solution(grid_state, shape_id)
    if result is None:
        return {
            'success': False,
            'message': 'No new solution found for this configuration.',
            'hint': None,
            'full_solution': None,
        }

    full_solution, _, removed = result
    hint = get_next_hint_piece(grid_state, full_solution, set(removed))
    if hint is None:
        return {
            'success': False,
            'message': 'Found a solution but could not determine the next piece.',
            'hint': None,
            'full_solution': full_solution,
        }

    removed_list = sorted(removed)
    message = f'Hint: place the {hint["piece_id"]} piece.'
    if removed_list:
        message += f' (Adjusted by ignoring misplaced piece(s): {", ".join(removed_list)})'

    return {
        'success': True,
        'message': message,
        'hint': hint,
        'full_solution': full_solution,
        'removed_pieces': removed_list,
    }