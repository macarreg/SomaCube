import { SOMA_PIECES, VALID_PIECES, SHAPE_IDS } from './constants.js';
import * as THREE from 'three';

export class UIController {
    constructor(pieceManager, gridManager) {
        this.pieceManager = pieceManager;
        this.gridManager = gridManager;
        this.currentShapeId = 'cube';
        this.initializeUI();
    }

    async initializeUI() {
        this.createShapeSelector();
        this.initializeEventListeners();
        await this.initializeSolutionCounts();
        const controls = document.querySelector('.controls');
        if (controls) {
            controls.style.visibility = 'visible';
        }
    }

    async initializeSolutionCounts() {
        try {
            await this.updateSolutionCounts();
        } catch (error) {
            console.error('Error initializing solution counts:', error);
        }
    }

    showMessage(message, duration = 2000) {
        const messageDiv = document.getElementById('message');
        if (messageDiv) {
            messageDiv.textContent = message;
            messageDiv.style.display = 'block';
            if (duration > 0) {
                setTimeout(() => messageDiv.style.display = 'none', duration);
            }
        }
    }

    initializeEventListeners() {
        const checkButton = document.getElementById('check-solution');
        const resetButton = document.getElementById('reset-grid');
        const removeButton = document.getElementById('remove-selected');
        
        if (checkButton) checkButton.addEventListener('click', () => this.checkSolution());
        if (resetButton) resetButton.addEventListener('click', () => this.resetGrid());
        if (removeButton) removeButton.addEventListener('click', () => this.pieceManager.removeSelectedPiece());
        window.addEventListener('keydown', (event) => this.handleKeyDown(event));
    }

    setShapeId(shapeId) {this.currentShapeId = shapeId;}

    handleKeyDown(event) {
        if (!this.pieceManager.selectedPiece) return;
        if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) {event.preventDefault();}
        
        const keyActions = {
            'ArrowLeft': () => this.pieceManager.movePiece('x', -1),
            'ArrowRight': () => this.pieceManager.movePiece('x', 1),
            'ArrowUp': () => this.pieceManager.movePiece('y', 1),
            'ArrowDown': () => this.pieceManager.movePiece('y', -1),
            'z': () => this.pieceManager.movePiece('z', -1),
            'x': () => this.pieceManager.movePiece('z', 1),
            'r': () => this.pieceManager.rotatePiece('x'),
            'f': () => this.pieceManager.rotatePiece('y'),
            'v': () => this.pieceManager.rotatePiece('z'),
            'Delete': () => this.pieceManager.removeSelectedPiece()
        };

        const action = keyActions[event.key];
        if (action) action();
    }

    async checkSolution() {
        const gridState = this.scanGridState();
        
        // Check if all valid grid spaces are filled
        const occupiedCells = this.gridManager.occupiedCells;
        
        for (const cell of occupiedCells) {
            const [x, y, z] = cell.split(',').map(Number);
            if (!gridState[x][y][z]) {
                this.showMessage('Please fill all cells in the grid');
                return false;
            }
        }
        
        const yassFormat = this.convertToYassFormat(gridState);
        
        try {
            const response = await fetch('/api/check-solution', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    grid_state: yassFormat,
                    shape_id: this.currentShapeId
                })
            });
            
            if (!response.ok) throw new Error('Failed to check solution');
            
            const data = await response.json();
            this.showMessage(data.message);
            
            if (data.valid) {
                await this.updateSolutionCounts();
            }
            
            return data.valid;
        } catch (error) {
            console.error('Error checking solution:', error);
            this.showMessage('Failed to check solution. Please try again.');
            return false;
        }
    }

    async resetGrid() {
        try {
            this.pieceManager.updatePiecesPanel();
            const success = await this.gridManager.loadGrid(this.currentShapeId);
            
            if (success) {
                await this.updateSolutionCounts();
                this.showMessage('Grid has been reset');
            } else {
                this.showMessage('Failed to reset grid');
            }
        } catch (error) {
            console.error('Error resetting grid:', error);
            this.showMessage('Error resetting grid');
        }
    }

    async updateSolutionCounts() {
        try {
            const [currentCount, totalCount] = await Promise.all([
                this.fetchCurrentSolutionCount(),
                this.fetchTotalSolutions()
            ]);
            
            this.updateSolutionCountDisplay(currentCount, totalCount);
            
            if (currentCount === totalCount && totalCount > 0) {
                this.showMessage('CONGRATULATIONS! YOU HAVE FOUND EVERY SOLUTION TO THIS PUZZLE!', 0);
            }
        } catch (error) {
            console.error('Error updating solution counts:', error);
        }
    }

    updateSolutionCountDisplay(currentCount, totalCount) {
        const countElement = document.getElementById('solution-count');
        const totalElement = document.getElementById('total-solutions');
        
        if (countElement) countElement.textContent = currentCount;
        if (totalElement) totalElement.textContent = totalCount;
    }

    async fetchCurrentSolutionCount() {
        const response = await fetch(`/api/solutions/${this.currentShapeId}`);
        if (!response.ok) return 0;
        const solutions = await response.json();
        return solutions.length;
    }

    async fetchTotalSolutions() {
        const response = await fetch(`/api/total-solutions/${this.currentShapeId}`);
        if (!response.ok) return 0;
        const data = await response.json();
        return data.total_solutions;
    }

    scanGridState() {
        const dimensions = this.gridManager.getDimensions();
        const currentState = Array(dimensions.width).fill().map(() => 
            Array(dimensions.height).fill().map(() => 
                Array(dimensions.depth).fill(null)
            )
        );
        
        this.pieceManager.renderer.scene.traverse(object => {
            if (object.isMesh && object.parent && object.parent.userData.pieceId) {
                const worldPos = new THREE.Vector3();
                object.getWorldPosition(worldPos);
                
                const gx = Math.floor(worldPos.x);
                const gy = Math.floor(worldPos.y);
                const gz = Math.floor(worldPos.z);
                
                if (gx >= 0 && gx < dimensions.width &&
                    gy >= 0 && gy < dimensions.height &&
                    gz >= 0 && gz < dimensions.depth) {
                    currentState[gx][gy][gz] = object.parent.userData.pieceId;
                }
            }
        });
        
        return currentState;
    }

    convertToYassFormat(gridState) {
        const dimensions = this.gridManager.getDimensions();
        let yassFormat = '';
        
        for (let z = 0; z < dimensions.depth; z++) {
            for (let y = 0; y < dimensions.height; y++) {
                for (let x = 0; x < dimensions.width; x++) {
                    const pieceId = gridState[x][y][z];
                    
                    if (this.gridManager.isOccupiedCell(x, y, z)) {
                        const originalCell = this.gridManager.getOriginalCell(x, y, z);
                        yassFormat += pieceId || originalCell;
                    } else {
                        yassFormat += '.';
                    }
                }
                yassFormat += '\n';
            }
            if (z < dimensions.depth - 1) {
                yassFormat += '\n';
            }
        }
        return yassFormat;
    }

    createShapeSelector() {
        const selectorContainer = document.getElementById('shape-selector');
        if (!selectorContainer) {
            console.error('Shape selector container not found');
            return;
        }

        const label = document.createElement('label');
        label.htmlFor = 'shape-select';
        label.textContent = 'Select Shape: ';
        
        const select = document.createElement('select');
        select.id = 'shape-select';
        
        SHAPE_IDS.forEach(shapeId => {
            const option = document.createElement('option');
            option.value = shapeId;
            option.textContent = shapeId.charAt(0).toUpperCase() + shapeId.slice(1);
            select.appendChild(option);
        });

        select.value = this.currentShapeId;
        
        select.addEventListener('change', async (e) => {
            const newShapeId = e.target.value;
            if (newShapeId !== this.currentShapeId) {
                try {
                    this.showMessage('Loading figure...');
                    this.pieceManager.updatePiecesPanel();
                    
                    const success = await this.gridManager.loadGrid(newShapeId);
                    if (success) {
                        this.setShapeId(newShapeId);
                        await this.updateSolutionCounts();
                        this.showMessage('Figure loaded successfully');
                    } else {
                        this.showMessage('Failed to load figure');
                        select.value = this.currentShapeId;
                    }
                } catch (error) {
                    console.error('Error loading figure:', error);
                    this.showMessage('Error loading figure');
                    select.value = this.currentShapeId;
                }
            }
        });

        selectorContainer.appendChild(label);
        selectorContainer.appendChild(select);
    }
} 