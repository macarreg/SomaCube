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
├── node_modules/            # Node.js dependencies (Three.js)
├── package.json            # Node.js project configuration
├── package-lock.json       # Node.js dependency lock file
└── requirements.txt        # Python dependencies
```

## Setup & Installation

### Prerequisites

- Python 3.6+ (Python 3.10+ recommended)
- Node.js 14+ and npm (for Three.js dependencies)
- Git

### Installation

1. Clone this repository:
   ```
   git clone https://github.com/BlakeMasters/Soma-Cube-Project.git
   cd soma-solver
   ```

2. Install Node.js dependencies:
   ```
   npm install
   ```
   This will install Three.js and other required frontend dependencies.

3. Compile the Yass solver using the included makefile:
   ```
   cd backend/yass
   make
   cd ../..
   ```

4. Play around with yass using different inputs and flags
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

## Development Notes

### Frontend Dependencies
The application uses Three.js for 3D rendering. The dependencies are managed through npm:
- Three.js is installed locally to ensure consistent versioning and faster loading
- The `node_modules` directory is git-ignored but the `package.json` and `package-lock.json` files are tracked
- When cloning the repository, run `npm install` to install all required dependencies

### Performance Optimization
- Three.js is served locally instead of from CDN for better performance
- The application includes loading indicators to provide feedback during initialization
- Dependencies are verified before the application starts

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

This project integrates the Yass SOMA Cube Solver by Mark R. Rubin, which is licensed under the GNU General Public License v3.0.

According to the license terms: This project, being a derivative work of a GPL-3.0 project, is also licensed under the GNU General Public License v3.0. You may copy, distribute, and modify this project under the terms of that license. A full copy of the license is included in the LICENSE file.
