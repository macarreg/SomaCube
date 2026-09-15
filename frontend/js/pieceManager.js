import * as THREE from 'three';
import { SOMA_PIECES, CELL_SIZE, PIECE_OPACITY, PIECE_HIGHLIGHT_OPACITY } from './constants.js';

export class PieceManager {
    constructor(renderer) {
        this.renderer = renderer;
        this.selectedPiece = null;
        this.placedPieces = new Map();
        this.initializePiecesPanel();
    }

    initializePiecesPanel() {
        const panel = document.getElementById('pieces-panel');
        if (!panel) return;

        const container = document.createElement('div');
        container.className = 'pieces-container';
        panel.appendChild(container);

        SOMA_PIECES.forEach(piece => {
            const element = this.createPieceElement(piece);
            container.appendChild(element);
        });
    }

    createPieceElement(piece) {
        const element = document.createElement('div');
        element.className = 'piece';
        element.id = `panel-${piece.id}`;
        element.innerHTML = `
            <div class="piece-preview" style="background-color: ${piece.color}"></div>
            <span>${piece.name}</span>
        `;
        element.onclick = () => this.selectOrCreatePiece(piece);
        return element;
    }

    // `shapeOverride` lets a piece be built from an arbitrary set of relative
    // cell offsets instead of its default (unrotated) baseShape. This is what
    // lets applyHint() reproduce the backend's exact target cells without
    // going through a separate (and previously mismatched) rotation search.
    createPieceMesh(piece, shapeOverride = null) {
        const group = new THREE.Group();
        const material = new THREE.MeshPhongMaterial({ 
            color: piece.color,
            transparent: true,
            opacity: PIECE_OPACITY,
            shininess: 30
        });

        const shape = shapeOverride || piece.baseShape;
        shape.forEach(([x, y, z]) => {
            const geometry = new THREE.BoxGeometry(CELL_SIZE, CELL_SIZE, CELL_SIZE);
            const cube = new THREE.Mesh(geometry, material);
            cube.position.set(x + 0.5, y + 0.5, z + 0.5);
            group.add(cube);
        });

        group.userData = {
            pieceId: piece.id,
            baseShape: piece.baseShape.map(cube => [...cube]),
            rotation: { x: 0, y: 0, z: 0 },
            originalColor: piece.color
        };

        return group;
    }

    selectOrCreatePiece(piece) {
        if (this.placedPieces.has(piece.id)) {
            this.selectExistingPiece(piece.id);
        } else {
            this.createNewPiece(piece);
        }
    }

    selectExistingPiece(pieceId) {
        if (this.selectedPiece) {
            this.setPieceHighlight(this.selectedPiece, false);
            this.highlightPanel(this.selectedPiece.userData.pieceId, false);
        }
        this.selectedPiece = this.placedPieces.get(pieceId);
        this.setPieceHighlight(this.selectedPiece, true);
        this.highlightPanel(pieceId, true);
    }

    createNewPiece(piece) {
        const mesh = this.createPieceMesh(piece);
        const centerPos = Math.floor(3 / 2); // Assuming 3x3x3 grid
        mesh.position.set(centerPos, centerPos, centerPos);
        this.renderer.scene.add(mesh);
        this.placedPieces.set(piece.id, mesh);
        
        if (this.selectedPiece) {
            this.setPieceHighlight(this.selectedPiece, false);
            this.highlightPanel(this.selectedPiece.userData.pieceId, false);
        }
        this.selectedPiece = mesh;
        this.setPieceHighlight(this.selectedPiece, true);
        this.highlightPanel(piece.id, true);
    }

    setPieceHighlight(mesh, highlight) {
        mesh.traverse(obj => {
            if (obj.isMesh && obj.material) {
                obj.material.opacity = highlight ? PIECE_HIGHLIGHT_OPACITY : PIECE_OPACITY;
            }
        });
    }

    highlightPanel(pieceId, highlight) {
        const el = document.getElementById(`panel-${pieceId}`);
        if (el) el.style.background = highlight ? '#e0e0e0' : '';
    }

    movePiece(axis, direction) {
        if (!this.selectedPiece) return;
        
        const newPos = this.selectedPiece.position.clone();
        newPos[axis] += direction;
        newPos[axis] = Math.round(newPos[axis]);        
        this.selectedPiece.position.copy(newPos);
    }

    rotatePiece(axis) {
        if (!this.selectedPiece) return;
        
        const rotation = this.selectedPiece.userData.rotation;
        rotation[axis] = (rotation[axis] + 90) % 360;
        
        this.selectedPiece.rotation.set(
            THREE.MathUtils.degToRad(rotation.x),
            THREE.MathUtils.degToRad(rotation.y),
            THREE.MathUtils.degToRad(rotation.z)
        );
    }

    removeSelectedPiece() {
        if (!this.selectedPiece) return;
        
        this.renderer.scene.remove(this.selectedPiece);
        this.placedPieces.delete(this.selectedPiece.userData.pieceId);
        this.selectedPiece = null;
    }

    removePieceById(pieceId) {
        const mesh = this.placedPieces.get(pieceId);
        if (!mesh) return;

        this.renderer.scene.remove(mesh);
        this.placedPieces.delete(pieceId);
        if (this.selectedPiece === mesh) {
            this.selectedPiece = null;
        }
        this.highlightPanel(pieceId, false);
    }

    removePiecesById(pieceIds) {
        pieceIds.forEach(pieceId => this.removePieceById(pieceId));
    }

    getPieceOccupiedCells(mesh) {
        const cells = new Set();
        mesh.updateMatrixWorld(true);
        mesh.traverse(object => {
            if (object.isMesh) {
                const worldPos = new THREE.Vector3();
                object.getWorldPosition(worldPos);
                cells.add(`${Math.floor(worldPos.x)},${Math.floor(worldPos.y)},${Math.floor(worldPos.z)}`);
            }
        });
        return cells;
    }

    // NOTE: there used to be a findPlacement() here that brute-forced every
    // (x, y, z) anchor combined with every 90-degree Euler rotation triple,
    // then compared floor(worldPosition) against the target cells.
    //
    // That was the root cause of "Found a solution but could not place the
    // hinted piece.": each cube's *local* position inside the group is offset
    // by +0.5 (e.g. (1.5, 0.5, 0.5)), and THREE.Object3D rotations are applied
    // about the group's local origin (0,0,0), not about the piece's own
    // bounding-box corner. Rotating those off-origin, half-integer points and
    // then flooring the result does NOT reproduce the backend's convention,
    // where every orientation is re-normalized (shifted so its own minimum
    // corner is (0,0,0)) before an integer anchor is added — see
    // hint_solver.py's _normalize_shape(). The two coordinate systems could
    // therefore land on completely different cells for the "same" rotation,
    // and many valid placements were never found at all.
    //
    // Since the backend already hands us the exact absolute target cells
    // (there is nothing left to "search" for), the fix is to stop trying to
    // discover a rotation and instead build the piece directly out of those
    // cells: normalize them into a relative shape anchored at their own
    // minimum corner, and place the group at that corner with zero rotation.
    // World-space cube centers then land exactly on target cell + 0.5, so
    // flooring always recovers the exact target cell — no ambiguity possible.
    applyHint(pieceId, targetCells) {
        const piece = SOMA_PIECES.find(p => p.id === pieceId);
        if (!piece) return false;

        const targetSet = new Set(targetCells.map(([x, y, z]) => `${x},${y},${z}`));

        if (this.placedPieces.has(pieceId)) {
            const existing = this.placedPieces.get(pieceId);
            const existingCells = this.getPieceOccupiedCells(existing);
            if (existingCells.size === targetSet.size &&
                [...targetSet].every(cell => existingCells.has(cell))) {
                this.selectExistingPiece(pieceId);
                return true;
            }
            this.renderer.scene.remove(existing);
            this.placedPieces.delete(pieceId);
        }

        if (!targetCells.length || targetCells.length !== piece.baseShape.length) {
            return false;
        }

        const minX = Math.min(...targetCells.map(c => c[0]));
        const minY = Math.min(...targetCells.map(c => c[1]));
        const minZ = Math.min(...targetCells.map(c => c[2]));
        const relativeShape = targetCells.map(([x, y, z]) => [x - minX, y - minY, z - minZ]);

        const mesh = this.createPieceMesh(piece, relativeShape);
        mesh.position.set(minX, minY, minZ);
        mesh.rotation.set(0, 0, 0);
        // The rotation is baked directly into relativeShape rather than into
        // an Object3D rotation, so the piece's "logical" rotation is 0. Manual
        // rotate/move controls continue to work from here exactly as they do
        // for any other placed piece.
        mesh.userData.rotation = { x: 0, y: 0, z: 0 };

        this.renderer.scene.add(mesh);
        this.placedPieces.set(pieceId, mesh);
        this.selectExistingPiece(pieceId);
        return true;
    }

    updatePiecesPanel() {
        this.placedPieces.clear();
        this.selectedPiece = null;
        
        SOMA_PIECES.forEach(piece => {
            this.highlightPanel(piece.id, false);
        });
        
        if (this.renderer && this.renderer.scene) {
            const objectsToRemove = [];
            this.renderer.scene.traverse(object => {
                if (object.isGroup && object.userData && object.userData.pieceId) {
                    objectsToRemove.push(object);
                }
            });
            
            objectsToRemove.forEach(object => {
                this.renderer.scene.remove(object);
            });
        }
    }
}