# SOMA Cube Puzzle Solver

A modern web-based application for visualizing, creating, and solving SOMA cube puzzles, integrating a 3D GUI with the YASS text-based solver.

## Overview

This application provides an interactive GUI for working with SOMA cube puzzles - a classic 3D puzzle consisting of 7 irregular pieces that can be assembled into a 3x3x3 cube. Users can:

- Visualize and manipulate SOMA cube pieces in 3D
- Build and validate custom SOMA cube configurations
- Get hints for solving difficult puzzles
- Generate and track all 240 unique solutions

The project combines a Flask backend that interfaces with the [Yass SOMA cube solver](https://github.com/thanks4opensource/yass) and a web-based frontend for user interaction.

## Project Structure

```
soma-solver/
├── backend/
│   ├── app.py               # Flask server and API endpoints
│   ├── parse_shapes.py      # Shape parsing and conversion utilities
│   ├── utils.py             # Solution normalization and validation
│   ├── solutions.json       # User-discovered solutions
│   └── yass/                # Yass solver (cloned from GitHub)
├── frontend/
│   ├── index.html           # Main HTML interface
│   ├── style.css            # Application styling
│   └── js/
│       ├── main.js          # Frontend application entry point
│       ├── constants.js     # Piece definitions and constants
│       ├── gridManager.js   # Grid logic and state
│       ├── pieceManager.js  # Piece management and UI
│       ├── renderer.js      # Three.js rendering logic
│       ├── uiController.js  # UI event handling and API calls
│       └── utils.js         # Frontend utility functions
└── requirements.txt         # Python dependencies
```

## Setup & Installation

### Prerequisites

- Python 3.6+ (Python 3.10+ recommended)
- Node.js (optional, for development)
- Git

### Installation

1. Clone this repository:
   ```
   git clone https://github.com/BlakeMasters/Soma-Cube-Project.git
   cd soma-solver
   ```

2. Compile the Yass solver using the included makefile:
   ```
   cd backend/yass
   make
   cd ../..
   ```

3. Play around with yass using different inputs and flags
   ```
   ./soma -h
   ./soma -a figures/cube.soma
   ```

### Running the Application

1. Setup a virtual environment
   ```
   python3 -m venv venv
   source venv/bin/activate
   ```

2. Install Python dependencies:
   ```
   pip3 install -r requirements.txt
   ```

3. Start the Flask server:
   ```
   cd backend
   python app.py
   ```

4. Open your browser and navigate to:
   ```
   http://localhost:5000
   ```

## Current Status

This application is currently in development with basic functionality implemented. The core features include:
- Web-based GUI for SOMA cube visualization
- Integration with the Yass solver for puzzle solutions
- Basic puzzle validation and hint system

## Future Plans

We plan to enhance the application with the following features:

- Implementing GUIs for varying solutions and pieces (pyramid, scorpion, 2x2x2)
- Hint function will display next viable piece on the grid
- User accounts to save puzzle progress
- Library of classic SOMA cube challenges
- Performance optimizations for larger puzzle configurations
- Additional puzzle statistics and analysis tools

## Credits

- [Yass SOMA Cube Solver](https://github.com/thanks4opensource/yass) - The backend solver engine used in this project. Developed by Mark R. Rubin
