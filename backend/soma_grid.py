import os
import logging
import json
from typing import Dict, List, Tuple, Set, Optional
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class GridDimensions:
    """Represents the dimensions of a 3D grid."""
    width: int
    height: int
    depth: int

    @classmethod
    def from_layers(cls, layers: List[str]) -> 'GridDimensions':
        """Create dimensions from layer data."""
        if not layers:
            raise ValueError("Empty layer data")
        first_layer = layers[0].strip().split('\n')
        return cls(
            width=len(first_layer[0]),
            height=len(first_layer),
            depth=len(layers)
        )

class SomaGrid:
    """Handles Soma grid operations and YASS format conversions."""
    
    OCCUPIED_CELLS = {'*', 'o'}
    
    def __init__(self, dimensions: GridDimensions, occupied_cells: Set[Tuple[int, int, int]], shape_id: Optional[str] = None):
        """Initialize a new SomaGrid instance."""
        self.dimensions = dimensions
        self.occupied_cells = occupied_cells
        self.shape_id = shape_id
    
    @classmethod
    def from_soma_file(cls, file_path: str) -> 'SomaGrid':
        """Create grid from .soma file."""
        with open(file_path, 'r') as f:
            content = f.read()
            shape_id = os.path.splitext(os.path.basename(file_path))[0]
            grid = cls.from_soma_content(content)
            grid.shape_id = shape_id
            return grid
    
    @classmethod
    def from_soma_content(cls, content: str) -> 'SomaGrid':
        """Create grid from YASS format content."""
        layers = content.strip().split('\n\n')
        if not layers:
            raise ValueError("Empty soma content")

        dimensions = GridDimensions.from_layers(layers)
        occupied_cells = cls._parse_occupied_cells(layers)
        return cls(dimensions, occupied_cells)

    @staticmethod
    def _parse_occupied_cells(layers: List[str]) -> Set[Tuple[int, int, int]]:
        """Parse occupied cells from layer data."""
        occupied_cells = set()
        for z, layer in enumerate(layers):
            for y, row in enumerate(layer.strip().split('\n')):
                for x, cell in enumerate(row):
                    if cell in SomaGrid.OCCUPIED_CELLS:
                        occupied_cells.add((x, y, z))
        return occupied_cells

    def get_solution_count(self) -> int:
        """Get the number of solutions found for this shape."""
        if not self.shape_id:
            return 0
            
        solutions_file = Path(__file__).parent / 'solutions' / f"{self.shape_id}_solutions.json"
        try:
            if not solutions_file.exists():
                return 0
            with open(solutions_file, 'r') as f:
                return len(json.load(f))
        except Exception as e:
            logger.error(f"Error getting solution count: {str(e)}")
            return 0

    def to_dict(self) -> Dict:
        """Convert grid to dictionary for API response."""
        figures_dir = os.path.join(os.path.dirname(__file__), 'yass', 'figures')
        shape_file = os.path.join(figures_dir, f"{self.shape_id}.soma")
        original_shape = ""
        if os.path.exists(shape_file):
            with open(shape_file, 'r') as f:
                original_shape = f.read().strip()

        return {
            'dimensions': {
                'width': self.dimensions.width,
                'height': self.dimensions.height,
                'depth': self.dimensions.depth
            },
            'occupied_cells': list(self.occupied_cells),
            'solution_count': self.get_solution_count(),
            'original_shape': original_shape
        }

    @staticmethod
    def get_available_shapes() -> List[Dict]:
        """Get list of available shapes."""
        shapes = []
        figures_dir = os.path.join(os.path.dirname(__file__), 'yass', 'figures')
        
        for file_name in os.listdir(figures_dir):
            if file_name.endswith('.soma'):
                try:
                    grid = SomaGrid.from_soma_file(os.path.join(figures_dir, file_name))
                    shapes.append({
                        'id': os.path.splitext(file_name)[0],
                        'name': os.path.splitext(file_name)[0].replace('_', ' ').title(),
                        'file': file_name,
                        'dimensions': grid.dimensions,
                        'occupied_cells': len(grid.occupied_cells)
                    })
                except Exception as e:
                    logger.error(f"Error loading shape {file_name}: {str(e)}")
        
        return shapes 