import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GRID_SIZE } from './constants.js';

export class Renderer {
    constructor() {
        this.scene = new THREE.Scene();
        this.camera = null;
        this.renderer = null;
        this.controls = null;
        this.raycaster = new THREE.Raycaster();
        this.mouse = new THREE.Vector2();
    }

    init() {
        const container = document.getElementById('container');
        if (!container) return;
    
        this.scene.background = new THREE.Color(0xf0f0f0);
    
        const { width, height } = this.getContainerSize();
    
        this.camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 1000);
        this.camera.position.set(5, 5, 5);
        this.camera.lookAt(0, 0, 0);
    
        this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.renderer.setSize(width, height, false); // false = let CSS size the canvas
        this.renderer.shadowMap.enabled = true;
    
        container.appendChild(this.renderer.domElement);
    
        this.setupLights();
        this.setupControls();
    
        this.resizeObserver = new ResizeObserver(() => this.onWindowResize());
        this.resizeObserver.observe(container);
    }
    
    getContainerSize() {
        const container = document.getElementById('container');
        return {
            width: Math.max(container?.clientWidth || 1, 1),
            height: Math.max(container?.clientHeight || 1, 1),
        };
    }
    
    onWindowResize() {
        if (!this.camera || !this.renderer) return;
    
        const { width, height } = this.getContainerSize();
        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(width, height, false);
    }
    
    onMouseMove(event) {
        if (!this.renderer) return;
        const rect = this.renderer.domElement.getBoundingClientRect();
        this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
        this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    }

    setupLights() {
        const ambientLight = new THREE.AmbientLight(0x404040, 0.5);
        this.scene.add(ambientLight);
        
        const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
        directionalLight.position.set(5, 5, 5);
        directionalLight.castShadow = true;
        this.scene.add(directionalLight);
    }

    setupControls() {
        this.controls = new OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.05;
        this.controls.screenSpacePanning = false;
        this.controls.minDistance = 3;
        this.controls.maxDistance = 20;
        this.controls.maxPolarAngle = Math.PI;
    }

    animate() {
        if (!this.scene || !this.camera || !this.renderer) return;
        
        requestAnimationFrame(() => this.animate());
        this.controls.update();
        this.renderer.render(this.scene, this.camera);
    }
} 