import * as THREE from 'three';
import { GridManager } from './gridManager.js';
import { PieceManager } from './pieceManager.js';
import { UIController } from './uiController.js';
import { Renderer } from './renderer.js';

class SomaSolver {
    constructor() {
        this.renderer = new Renderer();
        this.gridManager = null;
        this.pieceManager = null;
        this.uiController = null;
    }

    async init() {
        try {
            this.renderer.init();
            
            this.gridManager = new GridManager(this.renderer.scene);
            this.pieceManager = new PieceManager(this.renderer);
            this.uiController = new UIController(this.pieceManager, this.gridManager);

            window.uiController = this.uiController;

            // Sets default figure to cube, but we can use any figure in yass/figures or the new dropdown menu
            await this.gridManager.loadGrid('cube');

            window.addEventListener('resize', () => this.renderer.onWindowResize());
            window.addEventListener('mousemove', (e) => this.renderer.onMouseMove(e));
            
            this.renderer.animate();

        } catch (error) {
            console.error('Error initializing application:', error);
            alert('Failed to initialize application. Please refresh the page.');
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const app = new SomaSolver();
    app.init().catch(error => {
        console.error('Error starting application:', error);
        alert('Failed to start application. Please refresh the page.');
    });
});
