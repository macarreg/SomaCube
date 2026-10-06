import { SOMA_PIECES, VALID_PIECES, SHAPE_IDS } from './constants.js';
import * as THREE from 'three';

const KEY_TO_ACTION = {
    ArrowLeft: 'moveLeft',
    ArrowRight: 'moveRight',
    ArrowUp: 'moveUp',
    ArrowDown: 'moveDown',
    z: 'moveIn',
    x: 'moveOut',
    r: 'rotateX',
    f: 'rotateY',
    v: 'rotateZ',
    Delete: 'remove',
};

export class UIController {
    constructor(pieceManager, gridManager, authController) {
        this.pieceManager = pieceManager;
        this.gridManager = gridManager;
        this.authController = authController || null;
        this.currentShapeId = 'cube';
        this.cachedHintSolution = null;
        this.initializeUI();
    }

    _authHeaders() {
        const token = this.authController?.getAccessToken();
        return token ? { 'Authorization': `Bearer ${token}` } : {};
    }

    async initializeUI() {
        this.createShapeSelector();
        this.initializeEventListeners();
    
        const controls = document.querySelector('.controls');
        if (controls) controls.style.visibility = 'visible';
    
        await this.initializeSolutionCounts();   // slow call no longer gates the UI
    }

    async initializeSolutionCounts() {
        try {
            await this.updateSolutionCounts();
        } catch (error) {
            console.error('Error initializing solution counts:', error);
        }
    }

    initializeEventListeners() {
        const checkButton = document.getElementById('check-solution');
        const hintButton = document.getElementById('hint');
        const resetButton = document.getElementById('reset-grid');
        const removeButton = document.getElementById('remove-selected');
        
        if (checkButton) checkButton.addEventListener('click', () => this.checkSolution());
        if (hintButton) hintButton.addEventListener('click', () => this.requestHint());
        if (resetButton) resetButton.addEventListener('click', () => this.resetGrid());
        if (removeButton) removeButton.addEventListener('click', () => this.pieceManager.removeSelectedPiece());
        window.addEventListener('keydown', (event) => this.handleKeyDown(event));
        this.initializeTouchControls();
    }

    // One source of truth: keyboard and on-screen buttons both go through here.
    _controlActions() {
        const pm = this.pieceManager;
        return {
            moveLeft:  () => pm.movePiece('x', -1),
            moveRight: () => pm.movePiece('x', 1),
            moveUp:    () => pm.movePiece('y', 1),
            moveDown:  () => pm.movePiece('y', -1),
            moveIn:    () => pm.movePiece('z', -1),
            moveOut:   () => pm.movePiece('z', 1),
            rotateX:   () => pm.rotatePiece('x'),
            rotateY:   () => pm.rotatePiece('y'),
            rotateZ:   () => pm.rotatePiece('z'),
            remove:    () => pm.removeSelectedPiece(),
        };
    }

    runControlAction(actionName) {
        const action = this._controlActions()[actionName];
        if (action) action();
    }

    initializeTouchControls() {
        const panel = document.getElementById('piece-controls');
        if (!panel) return;
    
        panel.addEventListener('click', (event) => {
            const button = event.target.closest('[data-action]');
            if (!button) return;
    
            if (!this.pieceManager.selectedPiece) {
                this.showMessage('Tap a piece in the list first');
                return;
            }
            this.runControlAction(button.dataset.action);
        });
    }

    handleKeyDown(event) {
        // Don't hijack typing in the login form or the shape dropdown.
        const t = event.target;
        if (document.querySelector('.app--leaderboard')) return;
        if (t instanceof HTMLElement &&
            (t.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(t.tagName))) return;
        if (event.ctrlKey || event.metaKey || event.altKey) return;

        const actionName = KEY_TO_ACTION[event.key];
        if (!actionName || !this.pieceManager.selectedPiece) return;

        if (event.key.startsWith('Arrow')) event.preventDefault();
        this.runControlAction(actionName);
    }

    showMessage(message, duration = 3000) {
        const messageDiv = document.getElementById('message');
        if (!messageDiv) return;
    
        // 1. Cancel any pending timer so an old message can't hide this new one
        if (this.messageTimeout) {
            clearTimeout(this.messageTimeout);
            this.messageTimeout = null;
        }
    
        messageDiv.textContent = message;
        messageDiv.style.display = 'block';
    
        // 2. Set the fresh timer
        if (duration > 0) {
            this.messageTimeout = setTimeout(() => {
                messageDiv.style.display = 'none';
                messageDiv.textContent = '';
                this.messageTimeout = null;
            }, duration);
        }
    }

    setShapeId(shapeId) {this.currentShapeId = shapeId;}

    async _apiError(response, fallback) {
        let body = {};
        try { body = await response.json(); } catch {}
        if (response.status === 429) {
            const wait = response.headers.get('Retry-After');
            return `Too many requests. Please wait${wait ? ` ${wait}s` : ' a moment'} and try again.`;
        }
        if (response.status === 401) return 'Your session expired. Please log in again.';
        return body.message || body.error || fallback;
    }
    
    async refreshHintsCounter() {   // cheap: avoids re-running the soma subprocess
        const el = document.getElementById('hints-used-count');
        if (el) el.textContent = await this.fetchHintsUsed();
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
                headers: { 'Content-Type': 'application/json', ...this._authHeaders() },
                body: JSON.stringify({ 
                    grid_state: yassFormat,
                    shape_id: this.currentShapeId
                })
            });
            
            if (!response.ok) { this.showMessage(await this._apiError(response, 'Failed to check solution.')); return false; }
            
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

    clearHintCache() {
        this.cachedHintSolution = null;
    }

    extractPlacementsFromGridState(gridState) {
        const dimensions = this.gridManager.getDimensions();
        const placements = {};

        for (let x = 0; x < dimensions.width; x++) {
            for (let y = 0; y < dimensions.height; y++) {
                for (let z = 0; z < dimensions.depth; z++) {
                    const pieceId = gridState[x][y][z];
                    if (pieceId && VALID_PIECES.has(pieceId)) {
                        const key = `${x},${y},${z}`;
                        if (!placements[pieceId]) placements[pieceId] = new Set();
                        placements[pieceId].add(key);
                    }
                }
            }
        }
        return placements;
    }

    extractPlacementsFromYass(yassFormat) {
        const placements = {};
        const layers = yassFormat.trim().split('\n\n');

        layers.forEach((layer, z) => {
            layer.trim().split('\n').forEach((row, y) => {
                [...row].forEach((cell, x) => {
                    if (VALID_PIECES.has(cell)) {
                        const key = `${x},${y},${z}`;
                        if (!placements[cell]) placements[cell] = new Set();
                        placements[cell].add(key);
                    }
                });
            });
        });
        return placements;
    }

    applyHintResult(data) {
        if (data.removed_pieces?.length) {
            this.pieceManager.removePiecesById(data.removed_pieces);
        }

        const applied = this.pieceManager.applyHint(
            data.hint.piece_id,
            data.hint.cells,
            this.gridManager.getDimensions()
        );

        if (!applied) {
            this.showMessage('Found a solution but could not place the hinted piece.');
            return false;
        }

        this.cachedHintSolution = data.full_solution;
        this.showMessage(data.message);
        return true;
    }


    setHintsUsed(n) {
        const el = document.getElementById('hints-used-count');
        if (el && Number.isInteger(n)) el.textContent = n;
    }


    async requestHint() {
        const yassFormat = this.convertToYassFormat(this.scanGridState());
        try {
            this.showMessage('Finding hint...', 0);
            const response = await fetch('/api/hint', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', ...this._authHeaders() },
                body: JSON.stringify({ grid_state: yassFormat, shape_id: this.currentShapeId,
                                       cached_solution: this.cachedHintSolution }),
            });
            if (!response.ok) { this.showMessage(await this._apiError(response, 'Failed to get hint.')); return; }
            const data = await response.json();
            if (!data.success || !data.hint) { this.showMessage(data.message || 'No hint available.'); return; }
            if (this.applyHintResult(data)) {
                this.setHintsUsed(data.hints_used);
                if (!data.tracked && !this.authController?.getAccessToken()) {
                    this.showMessage(`${data.message} (Log in to track hints.)`);
                }
            }
        } catch (error) {
            console.error('Error getting hint:', error);
            this.showMessage('Failed to get hint. Please try again.');
        }
    }

    async resetGrid() {
        try {
            this.clearHintCache();
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

    updateSolutionCountDisplay(currentCount, totalCount) {
        const countElement = document.getElementById('solution-count');
        const totalElement = document.getElementById('total-solutions');
        
        if (countElement) countElement.textContent = currentCount;
        if (totalElement) totalElement.textContent = totalCount;
    }

    async fetchCurrentSolutionCount() {
        const response = await fetch(`/api/solutions/${this.currentShapeId}`, { headers: this._authHeaders() });
        if (!response.ok) return 0;
        const data = await response.json();
        return data.solution_count;
    }

    async fetchTotalSolutions() {
        const response = await fetch(`/api/total-solutions/${this.currentShapeId}`);
        if (!response.ok) return 0;
        const data = await response.json();
        return data.total_solutions;
    }

    async fetchHintsUsed() {
        const response = await fetch(`/api/stats/${this.currentShapeId}`, { headers: this._authHeaders() });
        if (!response.ok) return 0;
        const data = await response.json();
        return data.hints_used;
    }
    
    async updateSolutionCounts() {
        try {
            const [currentCount, totalCount, hintsUsed] = await Promise.all([
                this.fetchCurrentSolutionCount(),
                this.fetchTotalSolutions(),
                this.fetchHintsUsed(),
            ]);
            this.updateSolutionCountDisplay(currentCount, totalCount);
            const hintsEl = document.getElementById('hints-used-count');
            if (hintsEl) hintsEl.textContent = hintsUsed;
            if (currentCount === totalCount && totalCount > 0) {
                this.showMessage('CONGRATULATIONS! YOU HAVE FOUND EVERY SOLUTION TO THIS PUZZLE!', 0);
            }
        } catch (error) {
            console.error('Error updating solution counts:', error);
        }
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
                    this.clearHintCache();
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