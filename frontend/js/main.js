import { GridManager } from './gridManager.js';
import { PieceManager } from './pieceManager.js';
import { UIController } from './uiController.js';
import { Renderer } from './renderer.js';
import { AuthController } from './authController.js';
import { LeaderboardController } from './leaderboardController.js';

class SomaSolver {
    constructor() {
        this.renderer = new Renderer();
        this.gridManager = null;
        this.pieceManager = null;
        this.authController = null;
        this.uiController = null;
        this.leaderboardController = null;
    }

    async init() {
        try {
            this.renderer.init();
            this.gridManager = new GridManager(this.renderer.scene);
            this.pieceManager = new PieceManager(this.renderer);
            this.authController = new AuthController();
            this.uiController = new UIController(this.pieceManager, this.gridManager, this.authController);
            this.leaderboardController = new LeaderboardController(this.authController);
    
            window.uiController = this.uiController;
            window.addEventListener('mousemove', (e) => this.renderer.onMouseMove(e));
    
            // Grid + render loop come first: they only need our own backend.
            this.renderer.animate();
            const gridLoaded = await this.gridManager.loadGrid('cube');
            if (!gridLoaded) {
                this.uiController.showMessage('Failed to load the grid. Please refresh.', 0);
            }
    
            // Auth is optional: if Supabase is unreachable, keep playing anonymously.
            try {
                await this.authController.init(() => {
                    this.uiController.updateSolutionCounts();
                    this.leaderboardController.onAuthChange();
                });
            } catch (authError) {
                console.error('Auth unavailable, continuing anonymously:', authError);
                const status = document.getElementById('auth-status');
                if (status) status.textContent = 'Login is unavailable right now.';
            }
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
