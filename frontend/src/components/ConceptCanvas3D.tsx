import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';

export interface Concept3DProps {
  conceptType: 'transformer_architecture' | 'neural_network' | 'distributed_cluster' | 'molecule' | 'quantum_bloch' | 'generic';
  title?: string;
  description?: string;
}

interface LayerMetadata {
  id: string;
  title: string;
  shortName: string;
  color: string;
  hexColor: number;
  math: string;
  role: string;
  details: string;
}

// ── TRANSFORMER SPECIFIC ARCHITECTURAL STAGES ───────────────────────────────
const TRANSFORMER_STAGES: LayerMetadata[] = [
  {
    id: 'stage-embeddings',
    title: 'Input Token Embeddings & Positional Encoding',
    shortName: 'Token Embedding [E+P]',
    color: '#10B981',
    hexColor: 0x10b981,
    math: 'x_i = W_e(t_i) + PE(pos, 2i)',
    role: 'Vector Tokenization',
    details: 'Converts input words/tokens into dense 512-dim continuous vectors, adding sinusoidal wave positional frequencies so the model retains token order without recurrence.',
  },
  {
    id: 'stage-attention',
    title: 'Multi-Head Self-Attention Module (4 Parallel Heads)',
    shortName: 'Multi-Head Attention (Q,K,V)',
    color: '#8B5CF6',
    hexColor: 0x8b5cf6,
    math: 'MultiHead(Q,K,V) = Concat(head_1..head_4) W^O',
    role: 'Parallel Context Heads',
    details: 'Splits representations into 4 parallel attention heads across Query (Q), Key (K), and Value (V) projections. Calculates pairwise token affinity dot-products simultaneously in O(1) sequential operations.',
  },
  {
    id: 'stage-residual-1',
    title: 'Curved Residual Skip-Connection 1 (Add & Norm)',
    shortName: 'Residual Highway 1',
    color: '#38BDF8',
    hexColor: 0x38bdf8,
    math: 'x\' = LayerNorm(x + Sublayer(x))',
    role: 'Gradient Bypass Highway',
    details: 'The curved glowing bypass pipe looping OVER the attention block delivers input x directly to the LayerNorm slab, preventing vanishing gradients in deep Transformer stacks.',
  },
  {
    id: 'stage-ffn',
    title: 'Position-Wise Feed-Forward Network (FFN)',
    shortName: 'Feed-Forward [FFN]',
    color: '#EC4899',
    hexColor: 0xec4899,
    math: 'FFN(x\') = max(0, x\' W_1 + b_1) W_2 + b_2',
    role: 'Non-Linear Abstraction',
    details: 'Dense two-layer expansion (typically 4x d_model = 2048-dim) applied identically to each token position individually, followed by a secondary residual skip connection.',
  },
  {
    id: 'stage-output',
    title: 'Linear Unembedding & Softmax Probability Logits',
    shortName: 'Softmax Vocabulary Logits',
    color: '#F59E0B',
    hexColor: 0xf59e0b,
    math: 'P(w_t | w_<t) = softmax(W_vocab h_t)',
    role: 'Vocabulary Probability',
    details: 'Projects the final hidden states into vocabulary dimensions, passing through a temperature-controlled softmax to yield token probability distributions.',
  },
];

// ── STANDARD MULTI-LAYER PERCEPTRON (MLP) LAYERS ────────────────────────────
const MLP_LAYERS: LayerMetadata[] = [
  {
    id: 'mlp-input',
    title: 'Input Features Layer',
    shortName: 'Input Features (X)',
    color: '#10B981',
    hexColor: 0x10b981,
    math: 'a^[0] = x',
    role: 'Input Scalar Vector',
    details: 'Raw normalized input feature vectors passed to the first layer of the multi-layer perceptron.',
  },
  {
    id: 'mlp-hidden-1',
    title: 'Hidden Layer 1 (Dense ReLU)',
    shortName: 'Hidden Layer 1',
    color: '#8B5CF6',
    hexColor: 0x8b5cf6,
    math: 'z^[1] = W^[1] x + b^[1], a^[1] = ReLU(z^[1])',
    role: 'Feature Extraction',
    details: 'Dense fully connected layer applying affine transformation followed by rectified linear unit activation.',
  },
  {
    id: 'mlp-hidden-2',
    title: 'Hidden Layer 2 (Dense ReLU)',
    shortName: 'Hidden Layer 2',
    color: '#EC4899',
    hexColor: 0xec4899,
    math: 'z^[2] = W^[2] a^[1] + b^[2], a^[2] = ReLU(z^[2])',
    role: 'Deep Representations',
    details: 'Second dense layer forming hierarchical high-dimensional feature combinations.',
  },
  {
    id: 'mlp-output',
    title: 'Output Layer (Prediction Logits)',
    shortName: 'Output Logits (Y)',
    color: '#38BDF8',
    hexColor: 0x38bdf8,
    math: 'y_hat = sigma(W^[3] a^[2] + b^[3])',
    role: 'Prediction Head',
    details: 'Final linear transformation producing classification or regression target outputs.',
  },
];

const CLUSTER_ROLES: LayerMetadata[] = [
  {
    id: 'raft-leader',
    title: 'Raft Cluster Leader (Active Term 4)',
    shortName: 'Leader Node',
    color: '#F59E0B',
    hexColor: 0xf59e0b,
    math: 'Heartbeat Period: 50ms • Quorum >= 3/5',
    role: 'Consensus Coordinator',
    details: 'Receives write commands, manages the replicated log, broadcasts periodic heartbeats, and commits entries when a quorum responds.',
  },
  {
    id: 'raft-follower',
    title: 'Follower Replicas (Active Quorum)',
    shortName: 'Follower Quorum',
    color: '#38BDF8',
    hexColor: 0x38bdf8,
    math: 'Election Timeout: 150-300ms randomized',
    role: 'Distributed Replicas',
    details: 'Maintains state consistency. Replicates log entries from leader and initiates new leader election if heartbeats lapse.',
  },
];

const BLOCH_STATES: LayerMetadata[] = [
  {
    id: 'state-zero',
    title: 'Ground State |0⟩ (North Pole)',
    shortName: '|0⟩ State',
    color: '#38BDF8',
    hexColor: 0x38bdf8,
    math: '|0⟩ = [1, 0]^T',
    role: 'Computational Basis',
    details: 'Eigenstate of the Pauli-Z operator corresponding to spin-up or classical binary 0.',
  },
  {
    id: 'state-one',
    title: 'Excited State |1⟩ (South Pole)',
    shortName: '|1⟩ State',
    color: '#8B5CF6',
    hexColor: 0x8b5cf6,
    math: '|1⟩ = [0, 1]^T',
    role: 'Computational Basis',
    details: 'Eigenstate of the Pauli-Z operator corresponding to spin-down or classical binary 1.',
  },
  {
    id: 'state-psi',
    title: 'Superposition State Vector |ψ⟩',
    shortName: '|ψ⟩ Vector',
    color: '#F43F5E',
    hexColor: 0xf43f5e,
    math: '|ψ⟩ = cos(θ/2)|0⟩ + e^(iφ)sin(θ/2)|1⟩',
    role: 'Quantum Coherence',
    details: 'State vector on the Bloch sphere surface parameterized by polar angle θ and azimuthal phase angle φ.',
  },
];

// Helper: 3D Billboard Text Label Sprite
function createTextSprite(primary: string, secondary: string, color: string): THREE.Sprite {
  const canvas = document.createElement('canvas');
  canvas.width = 512;
  canvas.height = 140;
  const ctx = canvas.getContext('2d');
  if (ctx) {
    ctx.clearRect(0, 0, 512, 140);
    ctx.fillStyle = 'rgba(6, 10, 23, 0.9)';
    ctx.strokeStyle = color;
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.roundRect(10, 10, 492, 120, 24);
    ctx.fill();
    ctx.stroke();

    ctx.font = 'bold 34px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
    ctx.fillStyle = color;
    ctx.textAlign = 'center';
    ctx.fillText(primary, 256, 62);

    ctx.font = '500 22px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
    ctx.fillStyle = '#94A3B8';
    ctx.fillText(secondary, 256, 102);
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.minFilter = THREE.LinearFilter;
  const mat = new THREE.SpriteMaterial({ map: texture, transparent: true });
  const sprite = new THREE.Sprite(mat);
  sprite.scale.set(3.4, 0.95, 1);
  return sprite;
}

export const ConceptCanvas3D: React.FC<Concept3DProps> = ({
  conceptType = 'transformer_architecture',
  title,
  description,
}) => {
  const mountRef = useRef<HTMLDivElement>(null);
  const fullscreenMountRef = useRef<HTMLDivElement>(null);
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);
  const isTransformer = conceptType === 'transformer_architecture' || conceptType === 'generic';
  const activeStages = isTransformer ? TRANSFORMER_STAGES : conceptType === 'neural_network' ? MLP_LAYERS : [];

  const [selectedLayer, setSelectedLayer] = useState<LayerMetadata | null>(
    activeStages.length > 0 ? activeStages[0] : null
  );
  const [activeNodeInfo, setActiveNodeInfo] = useState<string | null>(null);
  const [isRotating, setIsRotating] = useState<boolean>(true);
  const [activeCameraPreset, setActiveCameraPreset] = useState<'perspective' | 'front' | 'isometric'>('perspective');

  const firePulseRef = useRef<(() => void) | null>(null);
  const setCameraAngleRef = useRef<((mode: 'perspective' | 'front' | 'isometric') => void) | null>(null);

  // Scene builder
  const setupThreeScene = (container: HTMLDivElement, isModal: boolean) => {
    const width = container.clientWidth || (isModal ? 800 : 400);
    const height = container.clientHeight || (isModal ? 540 : 290);

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x050914);

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    camera.position.set(0, 0, isModal ? 21 : 18);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    // 1. Ambient & Directional Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 1.0);
    scene.add(ambientLight);

    const cyanLight = new THREE.PointLight(0x38bdf8, 2.4, 80);
    cyanLight.position.set(16, 16, 16);
    scene.add(cyanLight);

    const purpleLight = new THREE.PointLight(0xa855f7, 2.2, 80);
    purpleLight.position.set(-16, -16, -16);
    scene.add(purpleLight);

    // Background Starfield Particles
    const starCount = 200;
    const starGeo = new THREE.BufferGeometry();
    const starPositions = new Float32Array(starCount * 3);
    for (let i = 0; i < starCount * 3; i += 3) {
      starPositions[i] = (Math.random() - 0.5) * 65;
      starPositions[i + 1] = (Math.random() - 0.5) * 50;
      starPositions[i + 2] = (Math.random() - 0.5) * 45 - 12;
    }
    starGeo.setAttribute('position', new THREE.BufferAttribute(starPositions, 3));
    const starMat = new THREE.PointsMaterial({ color: 0x38bdf8, size: 0.18, transparent: true, opacity: 0.45 });
    const starField = new THREE.Points(starGeo, starMat);
    scene.add(starField);

    const mainGroup = new THREE.Group();
    scene.add(mainGroup);
    const interactiveObjects: THREE.Object3D[] = [];

    // Synaptic / Residual pulse packets list
    interface PulsePacket {
      mesh: THREE.Mesh;
      curve?: THREE.CubicBezierCurve3;
      p1?: THREE.Vector3;
      p2?: THREE.Vector3;
      progress: number;
      speed: number;
      isCurve: boolean;
    }
    const pulsePackets: PulsePacket[] = [];
    const pulseGeo = new THREE.SphereGeometry(0.12, 12, 12);
    const pulseMat = new THREE.MeshBasicMaterial({ color: 0xffffff });

    // ── A. TRANSFORMER ARCHITECTURE (VASWANI ET AL.) ────────────────────────
    if (isTransformer) {
      // 1. Token Embeddings Stage (x = -7.0)
      const inputX = -7.0;
      const inputSprite = createTextSprite('INPUT EMBEDDINGS', 'Tokens + Positional Encoding (E+P)', '#10B981');
      inputSprite.position.set(inputX, 4.4, 0);
      mainGroup.add(inputSprite);

      const tokenNames = ['Token "The"', 'Token "Library"', 'Token "AI"'];
      const tokenPositions: THREE.Vector3[] = [];
      const tokenGeo = new THREE.CylinderGeometry(0.5, 0.5, 0.4, 20);
      const tokenMat = new THREE.MeshPhongMaterial({ color: 0x10b981, emissive: 0x059669, emissiveIntensity: 0.5 });

      tokenNames.forEach((name, i) => {
        const y = (i - 1) * 2.2;
        const pos = new THREE.Vector3(inputX, y, 0);
        tokenPositions.push(pos);

        const mesh = new THREE.Mesh(tokenGeo, tokenMat);
        mesh.position.copy(pos);
        mesh.rotation.x = Math.PI / 2;
        mesh.userData = {
          label: `${name} (512-dim Embedding Vector)`,
          meta: TRANSFORMER_STAGES[0],
        };
        mainGroup.add(mesh);
        interactiveObjects.push(mesh);
      });

      // Sinusoidal positional wave indicator
      const wavePoints: THREE.Vector3[] = [];
      for (let t = -3.0; t <= 3.0; t += 0.2) {
        wavePoints.push(new THREE.Vector3(inputX - 0.9, t, Math.sin(t * 2.0) * 0.4));
      }
      const waveGeo = new THREE.BufferGeometry().setFromPoints(wavePoints);
      const waveMat = new THREE.LineBasicMaterial({ color: 0x34d399, transparent: true, opacity: 0.75 });
      mainGroup.add(new THREE.Line(waveGeo, waveMat));

      // 2. Multi-Head Attention Module (x = -3.2)
      const mhaX = -3.2;
      const mhaSprite = createTextSprite('MULTI-HEAD ATTENTION', '4 Parallel Heads (Q, K, V)', '#8B5CF6');
      mhaSprite.position.set(mhaX, 4.4, 0);
      mainGroup.add(mhaSprite);

      // Q, K, V Projection Hubs
      const qkvLabels = [
        { label: 'Query Projection (Q)', color: 0xf59e0b, y: 1.6 },
        { label: 'Key Projection (K)', color: 0x38bdf8, y: 0.0 },
        { label: 'Value Projection (V)', color: 0xa855f7, y: -1.6 },
      ];
      const qkvPositions: THREE.Vector3[] = [];
      const qkvGeo = new THREE.SphereGeometry(0.42, 20, 20);

      qkvLabels.forEach((qkv) => {
        const pos = new THREE.Vector3(mhaX - 1.2, qkv.y, 0);
        qkvPositions.push(pos);
        const mat = new THREE.MeshPhongMaterial({ color: qkv.color, emissive: qkv.color, emissiveIntensity: 0.4 });
        const mesh = new THREE.Mesh(qkvGeo, mat);
        mesh.position.copy(pos);
        mesh.userData = { label: `${qkv.label} Matrix`, meta: TRANSFORMER_STAGES[1] };
        mainGroup.add(mesh);
        interactiveObjects.push(mesh);
      });

      // 4 Distinct Parallel Attention Heads
      const headColors = [0x06b6d4, 0x8b5cf6, 0xf43f5e, 0xf59e0b];
      const headPositions: THREE.Vector3[] = [];
      const headGeo = new THREE.SphereGeometry(0.38, 18, 18);

      headColors.forEach((color, hIdx) => {
        const y = (hIdx - 1.5) * 1.5;
        const z = (hIdx % 2 === 0 ? 1 : -1) * 0.9;
        const pos = new THREE.Vector3(mhaX + 0.6, y, z);
        headPositions.push(pos);

        const mat = new THREE.MeshPhongMaterial({ color, emissive: color, emissiveIntensity: 0.5 });
        const mesh = new THREE.Mesh(headGeo, mat);
        mesh.position.copy(pos);
        mesh.userData = { label: `Attention Head #${hIdx + 1} (softmax(QK^T / √d_k)V)`, meta: TRANSFORMER_STAGES[1] };
        mainGroup.add(mesh);
        interactiveObjects.push(mesh);

        // Connections from Q, K, V to Heads
        qkvPositions.forEach((qPos) => {
          const lGeo = new THREE.BufferGeometry().setFromPoints([qPos, pos]);
          const lMat = new THREE.LineBasicMaterial({ color: 0x64748b, transparent: true, opacity: 0.4 });
          mainGroup.add(new THREE.Line(lGeo, lMat));
        });
      });

      // Connections from Input Tokens to Q, K, V
      tokenPositions.forEach((tPos) => {
        qkvPositions.forEach((qPos) => {
          const lGeo = new THREE.BufferGeometry().setFromPoints([tPos, qPos]);
          const lMat = new THREE.LineBasicMaterial({ color: 0x10b981, transparent: true, opacity: 0.35 });
          mainGroup.add(new THREE.Line(lGeo, lMat));

          const pMesh = new THREE.Mesh(pulseGeo, pulseMat);
          mainGroup.add(pMesh);
          pulsePackets.push({
            mesh: pMesh,
            p1: tPos.clone(),
            p2: qPos.clone(),
            progress: Math.random(),
            speed: 0.009 + Math.random() * 0.008,
            isCurve: false,
          });
        });
      });

      // 3. Add & LayerNorm Slab 1 (x = 0.4)
      const norm1X = 0.4;
      const norm1Geo = new THREE.BoxGeometry(0.5, 4.4, 2.4);
      const norm1Mat = new THREE.MeshPhongMaterial({ color: 0x38bdf8, emissive: 0x0284c7, emissiveIntensity: 0.3, transparent: true, opacity: 0.85 });
      const norm1Mesh = new THREE.Mesh(norm1Geo, norm1Mat);
      norm1Mesh.position.set(norm1X, 0, 0);
      norm1Mesh.userData = { label: 'Add & LayerNorm 1: LayerNorm(x + Attention(x))', meta: TRANSFORMER_STAGES[2] };
      mainGroup.add(norm1Mesh);
      interactiveObjects.push(norm1Mesh);

      const norm1Sprite = createTextSprite('ADD & LAYERNORM 1', 'LayerNorm(x + Sublayer(x))', '#38BDF8');
      norm1Sprite.position.set(norm1X, 4.4, 0);
      mainGroup.add(norm1Sprite);

      // Connect Attention Heads to Norm 1
      headPositions.forEach((hPos) => {
        const dest = new THREE.Vector3(norm1X, hPos.y, 0);
        const lGeo = new THREE.BufferGeometry().setFromPoints([hPos, dest]);
        const lMat = new THREE.LineBasicMaterial({ color: 0x8b5cf6, transparent: true, opacity: 0.45 });
        mainGroup.add(new THREE.Line(lGeo, lMat));
      });

      // 4. THE ICONIC RESIDUAL SKIP-CONNECTION 1 (Curved Bypass Over Attention)
      const curve1 = new THREE.CubicBezierCurve3(
        new THREE.Vector3(inputX + 0.4, 0, 0),
        new THREE.Vector3(inputX + 2.0, 4.8, 1.2),
        new THREE.Vector3(norm1X - 2.0, 4.8, 1.2),
        new THREE.Vector3(norm1X, 0, 0)
      );
      const tube1Geo = new THREE.TubeGeometry(curve1, 32, 0.08, 8, false);
      const tube1Mat = new THREE.MeshPhongMaterial({ color: 0x38bdf8, emissive: 0x0284c7, emissiveIntensity: 0.6 });
      const tube1 = new THREE.Mesh(tube1Geo, tube1Mat);
      mainGroup.add(tube1);

      // Pulse along Residual Skip Connection 1
      for (let i = 0; i < 4; i++) {
        const pMesh = new THREE.Mesh(pulseGeo, pulseMat);
        mainGroup.add(pMesh);
        pulsePackets.push({
          mesh: pMesh,
          curve: curve1,
          progress: i * 0.25,
          speed: 0.012,
          isCurve: true,
        });
      }

      // 5. Feed-Forward Network FFN (x = 3.8)
      const ffnX = 3.8;
      const ffnSprite = createTextSprite('FEED-FORWARD NETWORK', 'FFN(x) = max(0, xW1 + b1)W2 + b2', '#EC4899');
      ffnSprite.position.set(ffnX, 4.4, 0);
      mainGroup.add(ffnSprite);

      const ffnNodeGeo = new THREE.SphereGeometry(0.4, 20, 20);
      const ffnMat = new THREE.MeshPhongMaterial({ color: 0xec4899, emissive: 0xbe185d, emissiveIntensity: 0.5 });
      const ffnPositions: THREE.Vector3[] = [];

      for (let i = 0; i < 4; i++) {
        const y = (i - 1.5) * 1.8;
        const pos = new THREE.Vector3(ffnX, y, 0);
        ffnPositions.push(pos);
        const mesh = new THREE.Mesh(ffnNodeGeo, ffnMat);
        mesh.position.copy(pos);
        mesh.userData = { label: `Feed-Forward Neuron #${i + 1} (GELU Expansion 2048-dim)`, meta: TRANSFORMER_STAGES[3] };
        mainGroup.add(mesh);
        interactiveObjects.push(mesh);

        // Connections from Norm1 to FFN
        const lGeo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(norm1X, y * 0.5, 0), pos]);
        const lMat = new THREE.LineBasicMaterial({ color: 0xec4899, transparent: true, opacity: 0.4 });
        mainGroup.add(new THREE.Line(lGeo, lMat));

        const pMesh = new THREE.Mesh(pulseGeo, pulseMat);
        mainGroup.add(pMesh);
        pulsePackets.push({
          mesh: pMesh,
          p1: new THREE.Vector3(norm1X, y * 0.5, 0),
          p2: pos.clone(),
          progress: Math.random(),
          speed: 0.01 + Math.random() * 0.006,
          isCurve: false,
        });
      }

      // 6. THE ICONIC RESIDUAL SKIP-CONNECTION 2 (Curved Bypass Over FFN)
      const norm2X = 6.2;
      const curve2 = new THREE.CubicBezierCurve3(
        new THREE.Vector3(norm1X + 0.4, 0, 0),
        new THREE.Vector3(norm1X + 2.0, 4.6, -1.2),
        new THREE.Vector3(norm2X - 1.5, 4.6, -1.2),
        new THREE.Vector3(norm2X, 0, 0)
      );
      const tube2Geo = new THREE.TubeGeometry(curve2, 32, 0.08, 8, false);
      const tube2Mat = new THREE.MeshPhongMaterial({ color: 0xec4899, emissive: 0xbe185d, emissiveIntensity: 0.6 });
      const tube2 = new THREE.Mesh(tube2Geo, tube2Mat);
      mainGroup.add(tube2);

      for (let i = 0; i < 4; i++) {
        const pMesh = new THREE.Mesh(pulseGeo, pulseMat);
        mainGroup.add(pMesh);
        pulsePackets.push({
          mesh: pMesh,
          curve: curve2,
          progress: i * 0.25,
          speed: 0.012,
          isCurve: true,
        });
      }

      // Add & LayerNorm Slab 2 (x = 6.2)
      const norm2Geo = new THREE.BoxGeometry(0.5, 4.4, 2.4);
      const norm2Mat = new THREE.MeshPhongMaterial({ color: 0xec4899, emissive: 0x9d174d, emissiveIntensity: 0.3, transparent: true, opacity: 0.85 });
      const norm2Mesh = new THREE.Mesh(norm2Geo, norm2Mat);
      norm2Mesh.position.set(norm2X, 0, 0);
      norm2Mesh.userData = { label: 'Add & LayerNorm 2: LayerNorm(x\' + FFN(x\'))', meta: TRANSFORMER_STAGES[2] };
      mainGroup.add(norm2Mesh);
      interactiveObjects.push(norm2Mesh);

      // Connect FFN to Norm 2
      ffnPositions.forEach((fPos) => {
        const dest = new THREE.Vector3(norm2X, fPos.y, 0);
        const lGeo = new THREE.BufferGeometry().setFromPoints([fPos, dest]);
        const lMat = new THREE.LineBasicMaterial({ color: 0xec4899, transparent: true, opacity: 0.45 });
        mainGroup.add(new THREE.Line(lGeo, lMat));
      });

      // 7. Output Softmax Logits Stage (x = 8.5)
      const outX = 8.5;
      const outSprite = createTextSprite('SOFTMAX LOGITS', 'P(w_t | w_<t) Vocabulary Distribution', '#F59E0B');
      outSprite.position.set(outX, 4.4, 0);
      mainGroup.add(outSprite);

      const probHeights = [2.2, 1.4, 0.7];
      const probLabels = ['Logit: "model" (P=0.68)', 'Logit: "system" (P=0.22)', 'Logit: "book" (P=0.10)'];
      probHeights.forEach((h, i) => {
        const y = (i - 1) * 2.0;
        const barGeo = new THREE.BoxGeometry(0.6, h, 0.6);
        const barMat = new THREE.MeshPhongMaterial({ color: 0xf59e0b, emissive: 0xd97706, emissiveIntensity: 0.5 });
        const mesh = new THREE.Mesh(barGeo, barMat);
        mesh.position.set(outX, y, 0);
        mesh.userData = { label: `${probLabels[i]}`, meta: TRANSFORMER_STAGES[4] };
        mainGroup.add(mesh);
        interactiveObjects.push(mesh);

        const lGeo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(norm2X, y, 0), mesh.position]);
        const lMat = new THREE.LineBasicMaterial({ color: 0xf59e0b, transparent: true, opacity: 0.5 });
        mainGroup.add(new THREE.Line(lGeo, lMat));
      });

      // Action: Fire Synchronized Transformer Energy Wave
      firePulseRef.current = () => {
        pulsePackets.forEach((p) => {
          p.progress = 0;
          p.speed = 0.024;
        });
      };
    }

    // ── B. CLASSICAL MULTI-LAYER PERCEPTRON (MLP) ───────────────────────────
    else if (conceptType === 'neural_network') {
      const layerCounts = [3, 4, 4, 2];
      const layerSpacing = 3.9;
      const nodeSpacing = 2.2;
      const nodePositions: THREE.Vector3[][] = [];
      const nodeGeo = new THREE.SphereGeometry(0.42, 24, 24);
      const haloGeo = new THREE.SphereGeometry(0.62, 16, 16);

      MLP_LAYERS.forEach((meta, lIdx) => {
        const count = layerCounts[lIdx];
        const layerNodes: THREE.Vector3[] = [];
        const x = (lIdx - (layerCounts.length - 1) / 2) * layerSpacing;

        const headerSprite = createTextSprite(meta.shortName, meta.role, meta.color);
        headerSprite.position.set(x, 4.4, 0);
        mainGroup.add(headerSprite);

        for (let i = 0; i < count; i++) {
          const y = (i - (count - 1) / 2) * nodeSpacing;
          const pos = new THREE.Vector3(x, y, 0);
          layerNodes.push(pos);

          const coreMat = new THREE.MeshPhongMaterial({
            color: meta.hexColor,
            emissive: meta.hexColor,
            emissiveIntensity: 0.45,
            shininess: 95,
          });
          const nodeMesh = new THREE.Mesh(nodeGeo, coreMat);
          nodeMesh.position.copy(pos);
          nodeMesh.userData = {
            layerId: meta.id,
            label: `${meta.title} (Neuron ${i + 1}/${count})`,
            meta,
          };
          mainGroup.add(nodeMesh);
          interactiveObjects.push(nodeMesh);

          const haloMat = new THREE.MeshBasicMaterial({
            color: meta.hexColor,
            transparent: true,
            opacity: 0.22,
            blending: THREE.AdditiveBlending,
          });
          const haloMesh = new THREE.Mesh(haloGeo, haloMat);
          haloMesh.position.copy(pos);
          mainGroup.add(haloMesh);
        }
        nodePositions.push(layerNodes);
      });

      for (let l = 0; l < nodePositions.length - 1; l++) {
        const sourceMeta = MLP_LAYERS[l];
        const lineMat = new THREE.LineBasicMaterial({
          color: sourceMeta.hexColor,
          transparent: true,
          opacity: 0.35,
        });

        for (const p1 of nodePositions[l]) {
          for (const p2 of nodePositions[l + 1]) {
            const geo = new THREE.BufferGeometry().setFromPoints([p1, p2]);
            const line = new THREE.Line(geo, lineMat);
            mainGroup.add(line);

            const pMesh = new THREE.Mesh(pulseGeo, pulseMat);
            mainGroup.add(pMesh);
            pulsePackets.push({
              mesh: pMesh,
              p1: p1.clone(),
              p2: p2.clone(),
              progress: Math.random(),
              speed: 0.008 + Math.random() * 0.007,
              isCurve: false,
            });
          }
        }
      }

      firePulseRef.current = () => {
        pulsePackets.forEach((p) => {
          p.progress = 0;
          p.speed = 0.022;
        });
      };
    } else if (conceptType === 'distributed_cluster') {
      const leaderGeo = new THREE.SphereGeometry(0.9, 28, 28);
      const leaderMat = new THREE.MeshPhongMaterial({ color: 0xf59e0b, emissive: 0xb45309, emissiveIntensity: 0.6, shininess: 100 });
      const leader = new THREE.Mesh(leaderGeo, leaderMat);
      leader.userData = { label: 'Raft Cluster Leader (Term 4)', meta: CLUSTER_ROLES[0] };
      mainGroup.add(leader);
      interactiveObjects.push(leader);

      const leaderSprite = createTextSprite('LEADER NODE', 'Raft Term 4 Coordinator', '#F59E0B');
      leaderSprite.position.set(0, 1.8, 0);
      mainGroup.add(leaderSprite);

      const followerCount = 5;
      const radius = 5.2;
      const followerGeo = new THREE.SphereGeometry(0.5, 20, 20);
      const followerMat = new THREE.MeshPhongMaterial({ color: 0x38bdf8, emissive: 0x0284c7, emissiveIntensity: 0.45, shininess: 85 });

      for (let i = 0; i < followerCount; i++) {
        const angle = (i / followerCount) * Math.PI * 2;
        const x = Math.cos(angle) * radius;
        const y = Math.sin(angle) * radius;
        const fMesh = new THREE.Mesh(followerGeo, followerMat);
        fMesh.position.set(x, y, 0);
        fMesh.userData = { label: `Raft Follower Node #${i + 1} (Quorum Active)`, meta: CLUSTER_ROLES[1] };
        mainGroup.add(fMesh);
        interactiveObjects.push(fMesh);

        const lineGeo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, 0, 0), fMesh.position]);
        const lineMat = new THREE.LineDashedMaterial({ color: 0x38bdf8, dashSize: 0.3, gapSize: 0.2 });
        const line = new THREE.Line(lineGeo, lineMat);
        line.computeLineDistances();
        mainGroup.add(line);
      }
    } else if (conceptType === 'quantum_bloch') {
      const sphereGeo = new THREE.SphereGeometry(4.4, 28, 28);
      const wireMat = new THREE.MeshBasicMaterial({ color: 0x38bdf8, wireframe: true, transparent: true, opacity: 0.22 });
      const sphere = new THREE.Mesh(sphereGeo, wireMat);
      mainGroup.add(sphere);

      const axes = new THREE.AxesHelper(5.8);
      mainGroup.add(axes);

      const poleGeo = new THREE.SphereGeometry(0.38, 18, 18);
      const northMat = new THREE.MeshPhongMaterial({ color: 0x38bdf8, emissive: 0x0284c7 });
      const northPole = new THREE.Mesh(poleGeo, northMat);
      northPole.position.set(0, 4.4, 0);
      northPole.userData = { label: 'State |0⟩ (North Pole)', meta: BLOCH_STATES[0] };
      mainGroup.add(northPole);
      interactiveObjects.push(northPole);

      const southMat = new THREE.MeshPhongMaterial({ color: 0x8b5cf6, emissive: 0x6d28d9 });
      const southPole = new THREE.Mesh(poleGeo, southMat);
      southPole.position.set(0, -4.4, 0);
      southPole.userData = { label: 'State |1⟩ (South Pole)', meta: BLOCH_STATES[1] };
      mainGroup.add(southPole);
      interactiveObjects.push(southPole);

      const stateVector = new THREE.Vector3(3.0, 3.0, 1.5).normalize().multiplyScalar(4.4);
      const arrowHelper = new THREE.ArrowHelper(stateVector.clone().normalize(), new THREE.Vector3(0, 0, 0), 4.4, 0xf43f5e, 0.7, 0.35);
      arrowHelper.userData = { label: 'Qubit State Vector |ψ⟩', meta: BLOCH_STATES[2] };
      mainGroup.add(arrowHelper);
      interactiveObjects.push(arrowHelper);
    }

    // Camera preset handler
    const applyCameraAngle = (mode: 'perspective' | 'front' | 'isometric') => {
      setActiveCameraPreset(mode);
      if (mode === 'front') {
        camera.position.set(0, 0, isModal ? 22 : 18);
        mainGroup.rotation.set(0, 0, 0);
      } else if (mode === 'isometric') {
        camera.position.set(14, 12, 18);
        camera.lookAt(0, 0, 0);
        mainGroup.rotation.set(0, 0, 0);
      } else {
        camera.position.set(0, 0, isModal ? 21 : 18);
        mainGroup.rotation.set(0.12, -0.22, 0);
      }
    };
    setCameraAngleRef.current = applyCameraAngle;
    applyCameraAngle('perspective');

    // Drag, Orbit & Raycasting
    let isDragging = false;
    let prevMousePos = { x: 0, y: 0 };

    const onMouseDown = (e: MouseEvent) => {
      isDragging = true;
      prevMousePos = { x: e.clientX, y: e.clientY };
    };

    const onMouseMove = (e: MouseEvent) => {
      if (isDragging) {
        const deltaX = e.clientX - prevMousePos.x;
        const deltaY = e.clientY - prevMousePos.y;
        mainGroup.rotation.y += deltaX * 0.008;
        mainGroup.rotation.x += deltaY * 0.008;
        prevMousePos = { x: e.clientX, y: e.clientY };
      }

      const rect = renderer.domElement.getBoundingClientRect();
      const mouse = new THREE.Vector2(
        ((e.clientX - rect.left) / rect.width) * 2 - 1,
        -((e.clientY - rect.top) / rect.height) * 2 + 1
      );

      const raycaster = new THREE.Raycaster();
      raycaster.setFromCamera(mouse, camera);
      const intersects = raycaster.intersectObjects(interactiveObjects, true);

      if (intersects.length > 0 && intersects[0].object.userData.label) {
        const target = intersects[0].object;
        setActiveNodeInfo(target.userData.label);
        if (target.userData.meta) {
          setSelectedLayer(target.userData.meta);
        }
      } else if (!isDragging) {
        setActiveNodeInfo(null);
      }
    };

    const onMouseUp = () => {
      isDragging = false;
    };

    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      camera.position.z = Math.max(7, Math.min(34, camera.position.z + e.deltaY * 0.02));
    };

    const dom = renderer.domElement;
    dom.addEventListener('mousedown', onMouseDown);
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    dom.addEventListener('wheel', onWheel, { passive: false });

    // Resize Handler
    const handleResize = () => {
      if (!container) return;
      const w = container.clientWidth;
      const h = container.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener('resize', handleResize);

    // Animation Loop with Synaptic & Residual Wave Pulses
    let animId: number;

    const animate = () => {
      animId = requestAnimationFrame(animate);

      if (isRotating && !isDragging) {
        mainGroup.rotation.y += 0.0035;
      }

      starField.rotation.y += 0.0005;

      for (const p of pulsePackets) {
        p.progress += p.speed;
        if (p.progress >= 1.0) {
          p.progress = 0;
        }

        if (p.isCurve && p.curve) {
          p.mesh.position.copy(p.curve.getPointAt(p.progress));
        } else if (p.p1 && p.p2) {
          p.mesh.position.lerpVectors(p.p1, p.p2, p.progress);
        }
      }

      renderer.render(scene, camera);
    };
    animate();

    return () => {
      cancelAnimationFrame(animId);
      dom.removeEventListener('mousedown', onMouseDown);
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
      dom.removeEventListener('wheel', onWheel);
      window.removeEventListener('resize', handleResize);
      if (container && dom.parentElement === container) {
        container.removeChild(dom);
      }
      renderer.dispose();
    };
  };

  useEffect(() => {
    if (!mountRef.current) return;
    return setupThreeScene(mountRef.current, false);
  }, [conceptType, isRotating]);

  useEffect(() => {
    if (!isFullscreen || !fullscreenMountRef.current) return;
    return setupThreeScene(fullscreenMountRef.current, true);
  }, [isFullscreen, conceptType, isRotating]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isFullscreen) {
        setIsFullscreen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isFullscreen]);

  return (
    <>
      {/* ── 1. INLINE 3D CARD (DRAWER VIEW) ─────────────────────────────────── */}
      <div
        style={{
          borderRadius: '12px',
          overflow: 'hidden',
          border: '1px solid rgba(56, 189, 248, 0.35)',
          background: '#070D1B',
          marginTop: '0.75rem',
          marginBottom: '0.75rem',
          boxShadow: '0 12px 32px rgba(0, 0, 0, 0.55)',
        }}
      >
        {/* Header Bar */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0.55rem 0.85rem',
            background: 'linear-gradient(90deg, rgba(14, 22, 38, 0.98), rgba(8, 13, 26, 0.98))',
            borderBottom: '1px solid rgba(56, 189, 248, 0.2)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
            <span style={{ fontSize: '1.05rem' }}>🪐</span>
            <div>
              <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#38BDF8', letterSpacing: '0.04em', textTransform: 'uppercase' }}>
                {title || (isTransformer ? 'TRANSFORMER & MULTI-HEAD ATTENTION ARCHITECTURE' : `3D Interactive Model: ${conceptType.replace('_', ' ')}`)}
              </div>
              <div style={{ fontSize: '0.62rem', color: '#64748B' }}>
                {isTransformer ? 'Attention Heads • Curved Residual Highways • Softmax Logits' : 'WebGL Architecture Engine • Real-time Synapse Pulses'}
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <button
              type="button"
              onClick={() => firePulseRef.current?.()}
              style={{
                fontSize: '0.65rem',
                padding: '0.2rem 0.55rem',
                borderRadius: '5px',
                border: '1px solid rgba(245, 158, 11, 0.4)',
                background: 'rgba(245, 158, 11, 0.15)',
                color: '#F59E0B',
                cursor: 'pointer',
                fontWeight: 600,
                display: 'inline-flex',
                alignItems: 'center',
                gap: '2px',
              }}
              title="Send a synchronized wave of energy across the Transformer network"
            >
              ⚡ Fire Signal
            </button>

            <button
              type="button"
              onClick={() => setIsRotating((prev) => !prev)}
              style={{
                fontSize: '0.65rem',
                padding: '0.2rem 0.5rem',
                borderRadius: '5px',
                border: '1px solid rgba(255, 255, 255, 0.15)',
                background: isRotating ? 'rgba(56, 189, 248, 0.15)' : 'transparent',
                color: isRotating ? '#38BDF8' : '#94A3B8',
                cursor: 'pointer',
                fontWeight: 500,
              }}
            >
              {isRotating ? '🔄 Rotate ON' : '⏸️ Paused'}
            </button>

            <button
              type="button"
              onClick={() => setIsFullscreen(true)}
              style={{
                fontSize: '0.68rem',
                padding: '0.25rem 0.65rem',
                borderRadius: '5px',
                border: '1px solid rgba(56, 189, 248, 0.45)',
                background: 'linear-gradient(135deg, rgba(56, 189, 248, 0.25), rgba(139, 92, 246, 0.25))',
                color: '#38BDF8',
                cursor: 'pointer',
                fontWeight: 600,
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.3rem',
                boxShadow: '0 2px 8px rgba(56, 189, 248, 0.25)',
              }}
              title="Open full-screen sandbox with interactive architectural inspector"
            >
              <span>⛶</span> Fullscreen Sandbox
            </button>
          </div>
        </div>

        {/* WebGL Canvas Mount */}
        <div
          ref={mountRef}
          style={{
            width: '100%',
            height: '290px',
            cursor: 'grab',
            position: 'relative',
          }}
        >
          <div
            style={{
              position: 'absolute',
              bottom: '10px',
              left: '10px',
              right: '10px',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              pointerEvents: 'none',
            }}
          >
            <span style={{ fontSize: '0.65rem', color: '#94A3B8', background: 'rgba(5, 9, 20, 0.85)', padding: '3px 8px', borderRadius: '4px', border: '1px solid rgba(255, 255, 255, 0.1)' }}>
              🖱️ Drag to rotate • Scroll to zoom • Arched tubes = Residual Skip Connections
            </span>
            {activeNodeInfo && (
              <span
                style={{
                  fontSize: '0.72rem',
                  fontWeight: 600,
                  color: '#38BDF8',
                  background: 'rgba(8, 13, 26, 0.95)',
                  border: '1px solid #38BDF8',
                  padding: '3px 10px',
                  borderRadius: '5px',
                  boxShadow: '0 4px 12px rgba(56, 189, 248, 0.35)',
                  animation: 'fadeIn 0.15s ease-out',
                }}
              >
                🎯 {activeNodeInfo}
              </span>
            )}
          </div>
        </div>

        {/* Layer Markings & Legend Bar */}
        {activeStages.length > 0 && (
          <div
            style={{
              padding: '0.55rem 0.75rem',
              background: 'rgba(10, 16, 31, 0.95)',
              borderTop: '1px solid rgba(56, 189, 248, 0.15)',
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
              gap: '0.4rem',
            }}
          >
            {activeStages.map((layer) => (
              <div
                key={layer.id}
                onClick={() => setSelectedLayer(layer)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  padding: '0.3rem 0.5rem',
                  borderRadius: '6px',
                  background: selectedLayer?.id === layer.id ? 'rgba(56, 189, 248, 0.15)' : 'rgba(255, 255, 255, 0.03)',
                  border: `1px solid ${selectedLayer?.id === layer.id ? layer.color : 'rgba(255, 255, 255, 0.06)'}`,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                <div style={{ width: '9px', height: '9px', borderRadius: '50%', background: layer.color, flexShrink: 0, boxShadow: `0 0 8px ${layer.color}` }} />
                <div style={{ overflow: 'hidden' }}>
                  <div style={{ fontSize: '0.68rem', fontWeight: 600, color: layer.color, whiteSpace: 'nowrap', textOverflow: 'ellipsis' }}>
                    {layer.shortName}
                  </div>
                  <div style={{ fontSize: '0.58rem', color: '#64748B' }}>
                    {layer.role}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Active Layer Mathematical Formula & Explanation */}
        {selectedLayer && (
          <div
            style={{
              padding: '0.6rem 0.85rem',
              background: 'rgba(6, 10, 23, 0.98)',
              borderTop: '1px solid rgba(255, 255, 255, 0.08)',
              fontSize: '0.72rem',
              color: '#CBD5E1',
              lineHeight: 1.5,
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
              <span style={{ fontWeight: 700, color: selectedLayer.color, fontSize: '0.75rem' }}>
                📐 {selectedLayer.title}
              </span>
              <code style={{ fontSize: '0.65rem', background: 'rgba(255, 255, 255, 0.08)', padding: '1px 6px', borderRadius: '4px', color: '#38BDF8' }}>
                {selectedLayer.math}
              </code>
            </div>
            <div>{selectedLayer.details}</div>
          </div>
        )}

        {description && (
          <div
            style={{
              padding: '0.45rem 0.85rem',
              fontSize: '0.7rem',
              color: '#94A3B8',
              background: 'rgba(8, 13, 26, 0.9)',
              borderTop: '1px solid rgba(255, 255, 255, 0.05)',
              lineHeight: 1.4,
            }}
          >
            💡 <strong style={{ color: '#E2E8F0' }}>Architecture Insight:</strong> {description}
          </div>
        )}
      </div>

      {/* ── 2. FULLSCREEN IMMERSIVE 3D SANDBOX MODAL ───────────────────────── */}
      {isFullscreen && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 99999,
            background: 'rgba(4, 7, 16, 0.97)',
            backdropFilter: 'blur(16px)',
            display: 'flex',
            flexDirection: 'column',
            padding: '1rem',
            animation: 'fadeIn 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
          }}
        >
          {/* Modal Header */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '0.75rem 1.25rem',
              background: 'linear-gradient(90deg, rgba(15, 23, 42, 0.98), rgba(8, 13, 26, 0.98))',
              border: '1px solid rgba(56, 189, 248, 0.35)',
              borderRadius: '12px 12px 0 0',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <div style={{ width: '38px', height: '38px', borderRadius: '8px', background: 'rgba(56, 189, 248, 0.15)', border: '1px solid rgba(56, 189, 248, 0.35)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.25rem' }}>
                🪐
              </div>
              <div>
                <h2 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#F8FAFC', margin: 0 }}>
                  {title || (isTransformer ? 'TRANSFORMER & MULTI-HEAD ATTENTION ARCHITECTURE (3D LAB)' : `Interactive 3D WebGL Concept Sandbox: ${conceptType.replace('_', ' ').toUpperCase()}`)}
                </h2>
                <div style={{ fontSize: '0.75rem', color: '#38BDF8', display: 'flex', gap: '0.8rem', marginTop: '2px' }}>
                  <span>Three.js WebGL 2.0 Shading</span>
                  <span>•</span>
                  <span>Curved Residual Highways</span>
                  <span>•</span>
                  <span>Parallel Attention Heads</span>
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <button
                type="button"
                onClick={() => firePulseRef.current?.()}
                style={{
                  fontSize: '0.8rem',
                  padding: '0.4rem 0.9rem',
                  borderRadius: '6px',
                  border: '1px solid rgba(245, 158, 11, 0.5)',
                  background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.25), rgba(217, 119, 6, 0.25))',
                  color: '#F59E0B',
                  cursor: 'pointer',
                  fontWeight: 700,
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '4px',
                  boxShadow: '0 0 12px rgba(245, 158, 11, 0.3)',
                }}
                title="Fire a high-intensity forward pass wave through the Transformer network"
              >
                ⚡ Fire Forward Pass
              </button>

              <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', background: 'rgba(255, 255, 255, 0.05)', padding: '2px 4px', borderRadius: '6px', border: '1px solid rgba(255, 255, 255, 0.1)' }}>
                <span style={{ fontSize: '0.68rem', color: '#64748B', paddingLeft: '4px' }}>Camera:</span>
                <button
                  type="button"
                  onClick={() => setCameraAngleRef.current?.('perspective')}
                  style={{
                    fontSize: '0.72rem',
                    padding: '0.25rem 0.55rem',
                    borderRadius: '4px',
                    border: 'none',
                    background: activeCameraPreset === 'perspective' ? 'rgba(56, 189, 248, 0.25)' : 'transparent',
                    color: activeCameraPreset === 'perspective' ? '#38BDF8' : '#94A3B8',
                    cursor: 'pointer',
                    fontWeight: 600,
                  }}
                >
                  Perspective
                </button>
                <button
                  type="button"
                  onClick={() => setCameraAngleRef.current?.('front')}
                  style={{
                    fontSize: '0.72rem',
                    padding: '0.25rem 0.55rem',
                    borderRadius: '4px',
                    border: 'none',
                    background: activeCameraPreset === 'front' ? 'rgba(56, 189, 248, 0.25)' : 'transparent',
                    color: activeCameraPreset === 'front' ? '#38BDF8' : '#94A3B8',
                    cursor: 'pointer',
                    fontWeight: 600,
                  }}
                >
                  Frontal
                </button>
                <button
                  type="button"
                  onClick={() => setCameraAngleRef.current?.('isometric')}
                  style={{
                    fontSize: '0.72rem',
                    padding: '0.25rem 0.55rem',
                    borderRadius: '4px',
                    border: 'none',
                    background: activeCameraPreset === 'isometric' ? 'rgba(56, 189, 248, 0.25)' : 'transparent',
                    color: activeCameraPreset === 'isometric' ? '#38BDF8' : '#94A3B8',
                    cursor: 'pointer',
                    fontWeight: 600,
                  }}
                >
                  Isometric
                </button>
              </div>

              <button
                type="button"
                onClick={() => setIsRotating((prev) => !prev)}
                style={{
                  fontSize: '0.8rem',
                  padding: '0.4rem 0.85rem',
                  borderRadius: '6px',
                  border: '1px solid rgba(255, 255, 255, 0.2)',
                  background: isRotating ? 'rgba(56, 189, 248, 0.2)' : 'rgba(255, 255, 255, 0.05)',
                  color: isRotating ? '#38BDF8' : '#94A3B8',
                  cursor: 'pointer',
                  fontWeight: 600,
                }}
              >
                {isRotating ? '🔄 Auto-Rotate ON' : '⏸️ Auto-Rotate Paused'}
              </button>

              <button
                type="button"
                onClick={() => setIsFullscreen(false)}
                style={{
                  fontSize: '0.8rem',
                  padding: '0.4rem 0.95rem',
                  borderRadius: '6px',
                  border: '1px solid rgba(239, 68, 68, 0.45)',
                  background: 'rgba(239, 68, 68, 0.18)',
                  color: '#F87171',
                  cursor: 'pointer',
                  fontWeight: 600,
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.35rem',
                }}
              >
                ✕ Exit Fullscreen (Esc)
              </button>
            </div>
          </div>

          {/* Modal Body: Split 70% 3D Viewport / 30% Architecture Inspector */}
          <div
            style={{
              flex: 1,
              display: 'flex',
              border: '1px solid rgba(56, 189, 248, 0.25)',
              borderTop: 'none',
              borderRadius: '0 0 12px 12px',
              overflow: 'hidden',
              background: '#040711',
            }}
          >
            {/* Left 70%: Massive WebGL Three.js Viewport */}
            <div
              ref={fullscreenMountRef}
              style={{
                flex: 1,
                position: 'relative',
                cursor: 'grab',
                height: '100%',
              }}
            >
              <div
                style={{
                  position: 'absolute',
                  top: '16px',
                  left: '16px',
                  background: 'rgba(8, 13, 26, 0.88)',
                  border: '1px solid rgba(255, 255, 255, 0.12)',
                  borderRadius: '8px',
                  padding: '8px 14px',
                  color: '#94A3B8',
                  fontSize: '0.75rem',
                  pointerEvents: 'none',
                  boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
                }}
              >
                🖱️ Left Click & Drag to Orbit • Scroll Wheel to Zoom • Notice Glowing Arched Tubes = Residual Skip Connections
              </div>

              {activeNodeInfo && (
                <div
                  style={{
                    position: 'absolute',
                    bottom: '24px',
                    left: '50%',
                    transform: 'translateX(-50%)',
                    background: 'rgba(15, 23, 42, 0.96)',
                    border: '1px solid #38BDF8',
                    borderRadius: '8px',
                    padding: '8px 22px',
                    color: '#38BDF8',
                    fontSize: '0.85rem',
                    fontWeight: 600,
                    boxShadow: '0 8px 24px rgba(56, 189, 248, 0.4)',
                    pointerEvents: 'none',
                  }}
                >
                  🎯 Selected Component: {activeNodeInfo}
                </div>
              )}
            </div>

            {/* Right 30%: Comprehensive Architectural Deep-Dive & Layer Inspector */}
            <div
              style={{
                width: '380px',
                borderLeft: '1px solid rgba(56, 189, 248, 0.2)',
                background: 'rgba(10, 16, 31, 0.98)',
                display: 'flex',
                flexDirection: 'column',
                overflowY: 'auto',
                padding: '1.25rem',
                gap: '1.25rem',
              }}
            >
              {/* Selected Component Card */}
              {selectedLayer ? (
                <div
                  style={{
                    background: 'rgba(15, 23, 42, 0.95)',
                    border: `1px solid ${selectedLayer.color}`,
                    borderRadius: '10px',
                    padding: '1.1rem',
                    boxShadow: `0 6px 24px rgba(0, 0, 0, 0.45)`,
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                    <div style={{ width: '12px', height: '12px', borderRadius: '50%', background: selectedLayer.color, boxShadow: `0 0 10px ${selectedLayer.color}` }} />
                    <span style={{ fontSize: '0.72rem', fontWeight: 700, color: selectedLayer.color, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                      {selectedLayer.role}
                    </span>
                  </div>
                  <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: '#F8FAFC', margin: '0 0 0.5rem 0' }}>
                    {selectedLayer.title}
                  </h3>
                  <div style={{ background: 'rgba(6, 10, 23, 0.95)', padding: '0.6rem 0.8rem', borderRadius: '6px', border: '1px solid rgba(255, 255, 255, 0.08)', marginBottom: '0.75rem' }}>
                    <div style={{ fontSize: '0.65rem', color: '#64748B', marginBottom: '3px' }}>MATHEMATICAL FORMULATION:</div>
                    <code style={{ fontSize: '0.78rem', color: '#38BDF8', wordBreak: 'break-all', fontWeight: 600 }}>
                      {selectedLayer.math}
                    </code>
                  </div>
                  <p style={{ fontSize: '0.8rem', color: '#CBD5E1', lineHeight: 1.55, margin: 0 }}>
                    {selectedLayer.details}
                  </p>
                </div>
              ) : (
                <div style={{ padding: '1rem', border: '1px dashed rgba(255, 255, 255, 0.15)', borderRadius: '10px', textAlign: 'center', color: '#64748B', fontSize: '0.8rem' }}>
                  Click or hover any component in the 3D model to inspect its parameters.
                </div>
              )}

              {/* Step-by-Step Architecture Pipeline */}
              {activeStages.length > 0 && (
                <div>
                  <h4 style={{ fontSize: '0.82rem', fontWeight: 700, color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.04em', margin: '0 0 0.65rem 0' }}>
                    {isTransformer ? 'Transformer Encoder Pipeline' : 'Perceptron Layers'}
                  </h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.55rem' }}>
                    {activeStages.map((layer, idx) => (
                      <div
                        key={layer.id}
                        onClick={() => setSelectedLayer(layer)}
                        style={{
                          padding: '0.7rem 0.9rem',
                          borderRadius: '8px',
                          background: selectedLayer?.id === layer.id ? 'rgba(56, 189, 248, 0.12)' : 'rgba(255, 255, 255, 0.02)',
                          border: `1px solid ${selectedLayer?.id === layer.id ? layer.color : 'rgba(255, 255, 255, 0.06)'}`,
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.75rem',
                          transition: 'all 0.15s ease',
                        }}
                      >
                        <div
                          style={{
                            width: '26px',
                            height: '26px',
                            borderRadius: '50%',
                            background: `${layer.color}25`,
                            border: `1px solid ${layer.color}`,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontSize: '0.75rem',
                            fontWeight: 700,
                            color: layer.color,
                            flexShrink: 0,
                          }}
                        >
                          {idx + 1}
                        </div>
                        <div style={{ overflow: 'hidden' }}>
                          <div style={{ fontSize: '0.78rem', fontWeight: 600, color: '#F1F5F9' }}>
                            {layer.shortName}
                          </div>
                          <div style={{ fontSize: '0.65rem', color: '#64748B' }}>
                            {layer.role}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Academic Teacher Defense Note */}
              <div
                style={{
                  marginTop: 'auto',
                  padding: '0.9rem',
                  borderRadius: '8px',
                  background: 'rgba(56, 189, 248, 0.05)',
                  border: '1px solid rgba(56, 189, 248, 0.18)',
                  fontSize: '0.75rem',
                  color: '#94A3B8',
                  lineHeight: 1.5,
                }}
              >
                🎓 <strong style={{ color: '#38BDF8' }}>Teacher Defense Note:</strong> In Vaswani et al. (2017), the Multi-Head Attention block fans out across parallel heads (d_k = d_model / h = 64) with residual connections (x + Sublayer(x)) preventing vanishing gradients in deep Transformer stacks.
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
