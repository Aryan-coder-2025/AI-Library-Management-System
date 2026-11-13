import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';

export interface Concept3DProps {
  conceptType: 'neural_network' | 'distributed_cluster' | 'molecule' | 'quantum_bloch' | 'generic';
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

const NEURAL_LAYERS: LayerMetadata[] = [
  {
    id: 'layer-0',
    title: 'Input Embeddings & Positional Encoding',
    shortName: 'Input [E+P]',
    color: '#10B981',
    hexColor: 0x10b981,
    math: 'x_i = Embedding(t_i) + PE(pos, 2i)',
    role: 'Vector Tokenization',
    details: 'Translates raw input tokens into dense d-dimensional embeddings (e.g. 512-dim). Injects sinusoidal positional encodings so the model understands token order without recurrence.',
  },
  {
    id: 'layer-1',
    title: 'Multi-Head Self-Attention Mechanism',
    shortName: 'Self-Attention [Q,K,V]',
    color: '#8B5CF6',
    hexColor: 0x8b5cf6,
    math: 'Attention(Q,K,V) = softmax(Q K^T / sqrt(d_k)) V',
    role: 'Contextual Head Attention',
    details: 'Projects representations into Queries, Keys, and Values across parallel heads. Computes pairwise dot-product compatibility scores to capture dynamic grammatical and semantic dependencies.',
  },
  {
    id: 'layer-2',
    title: 'Position-Wise Feed-Forward & Add/Norm',
    shortName: 'Feed-Forward [FFN]',
    color: '#EC4899',
    hexColor: 0xec4899,
    math: 'FFN(x) = max(0, x W_1 + b_1) W_2 + b_2',
    role: 'Non-Linear Abstraction',
    details: 'Two dense affine linear transformations with GELU/ReLU non-linearity, bracketed by residual skip connections and LayerNorm (LayerNorm(x + SubLayer(x))) to guarantee stable gradient flow.',
  },
  {
    id: 'layer-3',
    title: 'Linear Projection & Softmax Logits',
    shortName: 'Softmax Output',
    color: '#38BDF8',
    hexColor: 0x38bdf8,
    math: 'P(w_t | w_<t) = softmax(W_vocab h_t)',
    role: 'Vocabulary Probability',
    details: 'Unembeds final hidden representations back into vocabulary logits, passing through a softmax temperature function to generate output next-token probability distributions.',
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
    details: 'Receives all write commands from patrons, appends log entries, replicates them to follower nodes, and commits when a majority acknowledges.',
  },
  {
    id: 'raft-follower',
    title: 'Follower Replicas (Active Quorum)',
    shortName: 'Follower Quorum',
    color: '#38BDF8',
    hexColor: 0x38bdf8,
    math: 'Election Timeout: 150-300ms randomized',
    role: 'Distributed Replicas',
    details: 'Passive nodes that respond to leader heartbeats and log entries. If a heartbeat is missed, a follower steps up to Candidate state.',
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
    details: 'Represents a pure state vector on the sphere surface parameterized by polar angle θ and azimuthal phase angle φ.',
  },
];

export const ConceptCanvas3D: React.FC<Concept3DProps> = ({
  conceptType = 'neural_network',
  title,
  description,
}) => {
  const mountRef = useRef<HTMLDivElement>(null);
  const fullscreenMountRef = useRef<HTMLDivElement>(null);
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);
  const [selectedLayer, setSelectedLayer] = useState<LayerMetadata | null>(
    conceptType === 'neural_network' ? NEURAL_LAYERS[0] : null
  );
  const [activeNodeInfo, setActiveNodeInfo] = useState<string | null>(null);
  const [isRotating, setIsRotating] = useState<boolean>(true);

  // Setup Three.js scene builder
  const setupThreeScene = (container: HTMLDivElement, isModal: boolean) => {
    const width = container.clientWidth || (isModal ? 800 : 400);
    const height = container.clientHeight || (isModal ? 520 : 280);

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x060a17);

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    camera.position.set(0, 0, isModal ? 19 : 17);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    // Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.9);
    scene.add(ambientLight);

    const pointLight1 = new THREE.PointLight(0x38bdf8, 2, 60);
    pointLight1.position.set(12, 12, 12);
    scene.add(pointLight1);

    const pointLight2 = new THREE.PointLight(0xa855f7, 1.8, 60);
    pointLight2.position.set(-12, -12, -12);
    scene.add(pointLight2);

    const mainGroup = new THREE.Group();
    scene.add(mainGroup);
    const interactiveObjects: THREE.Object3D[] = [];

    // Geometry Construction
    if (conceptType === 'neural_network') {
      const layerCounts = [3, 4, 4, 2];
      const layerSpacing = 3.8;
      const nodeSpacing = 2.1;
      const nodePositions: THREE.Vector3[][] = [];
      const nodeGeo = new THREE.SphereGeometry(0.38, 20, 20);

      NEURAL_LAYERS.forEach((meta, lIdx) => {
        const count = layerCounts[lIdx];
        const layerNodes: THREE.Vector3[] = [];
        const x = (lIdx - (layerCounts.length - 1) / 2) * layerSpacing;
        const mat = new THREE.MeshPhongMaterial({
          color: meta.hexColor,
          emissive: meta.hexColor,
          emissiveIntensity: 0.35,
          shininess: 90,
        });

        for (let i = 0; i < count; i++) {
          const y = (i - (count - 1) / 2) * nodeSpacing;
          const pos = new THREE.Vector3(x, y, 0);
          layerNodes.push(pos);

          const mesh = new THREE.Mesh(nodeGeo, mat);
          mesh.position.copy(pos);
          mesh.userData = {
            layerId: meta.id,
            label: `${meta.title} (Node ${i + 1}/${count})`,
            meta,
          };
          mainGroup.add(mesh);
          interactiveObjects.push(mesh);
        }
        nodePositions.push(layerNodes);
      });

      // Synapse Connections with glow opacity
      const lineMat = new THREE.LineBasicMaterial({ color: 0x334155, transparent: true, opacity: 0.55 });
      for (let l = 0; l < nodePositions.length - 1; l++) {
        for (const p1 of nodePositions[l]) {
          for (const p2 of nodePositions[l + 1]) {
            const geo = new THREE.BufferGeometry().setFromPoints([p1, p2]);
            const line = new THREE.Line(geo, lineMat);
            mainGroup.add(line);
          }
        }
      }
    } else if (conceptType === 'distributed_cluster') {
      const leaderGeo = new THREE.SphereGeometry(0.85, 28, 28);
      const leaderMat = new THREE.MeshPhongMaterial({ color: 0xf59e0b, emissive: 0xb45309, emissiveIntensity: 0.5, shininess: 100 });
      const leader = new THREE.Mesh(leaderGeo, leaderMat);
      leader.userData = { label: 'Raft Leader Node (Active Term 4)', meta: CLUSTER_ROLES[0] };
      mainGroup.add(leader);
      interactiveObjects.push(leader);

      const followerCount = 5;
      const radius = 4.8;
      const followerGeo = new THREE.SphereGeometry(0.48, 20, 20);
      const followerMat = new THREE.MeshPhongMaterial({ color: 0x38bdf8, emissive: 0x0284c7, emissiveIntensity: 0.4, shininess: 80 });

      for (let i = 0; i < followerCount; i++) {
        const angle = (i / followerCount) * Math.PI * 2;
        const x = Math.cos(angle) * radius;
        const y = Math.sin(angle) * radius;
        const fMesh = new THREE.Mesh(followerGeo, followerMat);
        fMesh.position.set(x, y, 0);
        fMesh.userData = { label: `Raft Follower Node #${i + 1} (Quorum Active)`, meta: CLUSTER_ROLES[1] };
        mainGroup.add(fMesh);
        interactiveObjects.push(fMesh);

        // Heartbeat lines
        const lineGeo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, 0, 0), fMesh.position]);
        const lineMat = new THREE.LineDashedMaterial({ color: 0x38bdf8, dashSize: 0.3, gapSize: 0.2 });
        const line = new THREE.Line(lineGeo, lineMat);
        line.computeLineDistances();
        mainGroup.add(line);
      }
    } else if (conceptType === 'quantum_bloch') {
      const sphereGeo = new THREE.SphereGeometry(4.2, 24, 24);
      const wireMat = new THREE.MeshBasicMaterial({ color: 0x38bdf8, wireframe: true, transparent: true, opacity: 0.22 });
      const sphere = new THREE.Mesh(sphereGeo, wireMat);
      mainGroup.add(sphere);

      // Axes
      const axesHelper = new THREE.AxesHelper(5.5);
      mainGroup.add(axesHelper);

      // Poles
      const poleGeo = new THREE.SphereGeometry(0.35, 16, 16);
      const northMat = new THREE.MeshPhongMaterial({ color: 0x38bdf8, emissive: 0x0284c7 });
      const northPole = new THREE.Mesh(poleGeo, northMat);
      northPole.position.set(0, 4.2, 0);
      northPole.userData = { label: 'State |0⟩ (North Pole)', meta: BLOCH_STATES[0] };
      mainGroup.add(northPole);
      interactiveObjects.push(northPole);

      const southMat = new THREE.MeshPhongMaterial({ color: 0x8b5cf6, emissive: 0x6d28d9 });
      const southPole = new THREE.Mesh(poleGeo, southMat);
      southPole.position.set(0, -4.2, 0);
      southPole.userData = { label: 'State |1⟩ (South Pole)', meta: BLOCH_STATES[1] };
      mainGroup.add(southPole);
      interactiveObjects.push(southPole);

      // Superposition Vector
      const stateVector = new THREE.Vector3(2.8, 2.8, 1.4).normalize().multiplyScalar(4.2);
      const arrowHelper = new THREE.ArrowHelper(stateVector.clone().normalize(), new THREE.Vector3(0, 0, 0), 4.2, 0xf43f5e, 0.6, 0.3);
      arrowHelper.userData = { label: 'Qubit State Vector |ψ⟩', meta: BLOCH_STATES[2] };
      mainGroup.add(arrowHelper);
      interactiveObjects.push(arrowHelper);
    } else {
      // Molecule or Generic fallback
      const cGeo = new THREE.SphereGeometry(0.6, 20, 20);
      const cMat = new THREE.MeshPhongMaterial({ color: 0x38bdf8, emissive: 0x0369a1 });
      for (let i = 0; i < 6; i++) {
        const ang = (i / 6) * Math.PI * 2;
        const mesh = new THREE.Mesh(cGeo, cMat);
        mesh.position.set(Math.cos(ang) * 3.5, Math.sin(ang) * 3.5, 0);
        mesh.userData = { label: `Benzene Carbon-C${i + 1} (sp² hybridized)` };
        mainGroup.add(mesh);
        interactiveObjects.push(mesh);
      }
    }

    // Interaction Handlers
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
        mainGroup.rotation.y += deltaX * 0.01;
        mainGroup.rotation.x += deltaY * 0.01;
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
      camera.position.z = Math.max(7, Math.min(32, camera.position.z + e.deltaY * 0.02));
    };

    const dom = renderer.domElement;
    dom.addEventListener('mousedown', onMouseDown);
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    dom.addEventListener('wheel', onWheel, { passive: false });

    // Handle container resize
    const handleResize = () => {
      if (!container) return;
      const w = container.clientWidth;
      const h = container.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener('resize', handleResize);

    // Animation Loop
    let animId: number;
    const animate = () => {
      animId = requestAnimationFrame(animate);
      if (isRotating && !isDragging) {
        mainGroup.rotation.y += 0.005;
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

  // Inline mount effect
  useEffect(() => {
    if (!mountRef.current) return;
    return setupThreeScene(mountRef.current, false);
  }, [conceptType, isRotating]);

  // Fullscreen modal mount effect
  useEffect(() => {
    if (!isFullscreen || !fullscreenMountRef.current) return;
    return setupThreeScene(fullscreenMountRef.current, true);
  }, [isFullscreen, conceptType, isRotating]);

  // Keyboard close for fullscreen (Esc)
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
          border: '1px solid rgba(56, 189, 248, 0.3)',
          background: '#070D1B',
          marginTop: '0.75rem',
          marginBottom: '0.75rem',
          boxShadow: '0 12px 32px rgba(0, 0, 0, 0.5)',
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
            <span style={{ fontSize: '1rem' }}>🪐</span>
            <div>
              <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#38BDF8', letterSpacing: '0.04em', textTransform: 'uppercase' }}>
                {title || `3D Interactive Model: ${conceptType.replace('_', ' ')}`}
              </div>
              <div style={{ fontSize: '0.62rem', color: '#64748B' }}>
                WebGL Architecture Engine • Interactive Orbit
              </div>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
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
                border: '1px solid rgba(56, 189, 248, 0.4)',
                background: 'linear-gradient(135deg, rgba(56, 189, 248, 0.25), rgba(139, 92, 246, 0.25))',
                color: '#38BDF8',
                cursor: 'pointer',
                fontWeight: 600,
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.3rem',
                boxShadow: '0 2px 8px rgba(56, 189, 248, 0.2)',
              }}
              title="Expand into full-screen sandbox with interactive architectural inspector"
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
            height: '280px',
            cursor: 'grab',
            position: 'relative',
          }}
        >
          {/* Canvas Floating Overlay Controls & Tooltip */}
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
              🖱️ Drag to rotate • Scroll to zoom
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
                  boxShadow: '0 4px 12px rgba(56, 189, 248, 0.3)',
                  animation: 'fadeIn 0.15s ease-out',
                }}
              >
                🎯 {activeNodeInfo}
              </span>
            )}
          </div>
        </div>

        {/* Layer Markings & Legend Bar */}
        {conceptType === 'neural_network' && (
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
            {NEURAL_LAYERS.map((layer) => (
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
            background: 'rgba(5, 9, 20, 0.96)',
            backdropFilter: 'blur(16px)',
            display: 'flex',
            flexDirection: 'column',
            padding: '1.25rem',
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
              background: 'linear-gradient(90deg, rgba(15, 23, 42, 0.95), rgba(8, 13, 26, 0.95))',
              border: '1px solid rgba(56, 189, 248, 0.3)',
              borderRadius: '12px 12px 0 0',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <div style={{ width: '36px', height: '36px', borderRadius: '8px', background: 'rgba(56, 189, 248, 0.15)', border: '1px solid rgba(56, 189, 248, 0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.2rem' }}>
                🪐
              </div>
              <div>
                <h2 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#F8FAFC', margin: 0 }}>
                  {title || `Interactive 3D WebGL Concept Sandbox: ${conceptType.replace('_', ' ').toUpperCase()}`}
                </h2>
                <div style={{ fontSize: '0.75rem', color: '#38BDF8', display: 'flex', gap: '0.8rem', marginTop: '2px' }}>
                  <span>WebGL 2.0 Real-time Shading</span>
                  <span>•</span>
                  <span>Three.js Orbit Controls</span>
                  <span>•</span>
                  <span>Full Architectural Raycasting</span>
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
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
                  border: '1px solid rgba(239, 68, 68, 0.4)',
                  background: 'rgba(239, 68, 68, 0.15)',
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
              {/* On-Canvas Hint Overlays */}
              <div
                style={{
                  position: 'absolute',
                  top: '16px',
                  left: '16px',
                  background: 'rgba(8, 13, 26, 0.85)',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  borderRadius: '8px',
                  padding: '8px 14px',
                  color: '#94A3B8',
                  fontSize: '0.75rem',
                  pointerEvents: 'none',
                }}
              >
                🖱️ Left Click & Drag to Orbit • Scroll Wheel to Zoom • Hover or Click Nodes to Inspect
              </div>

              {activeNodeInfo && (
                <div
                  style={{
                    position: 'absolute',
                    bottom: '20px',
                    left: '50%',
                    transform: 'translateX(-50%)',
                    background: 'rgba(15, 23, 42, 0.95)',
                    border: '1px solid #38BDF8',
                    borderRadius: '8px',
                    padding: '8px 20px',
                    color: '#38BDF8',
                    fontSize: '0.85rem',
                    fontWeight: 600,
                    boxShadow: '0 8px 24px rgba(56, 189, 248, 0.35)',
                    pointerEvents: 'none',
                  }}
                >
                  🎯 Selected Node: {activeNodeInfo}
                </div>
              )}
            </div>

            {/* Right 30%: Comprehensive Architectural Deep-Dive & Layer Inspector */}
            <div
              style={{
                width: '360px',
                borderLeft: '1px solid rgba(56, 189, 248, 0.2)',
                background: 'rgba(10, 16, 31, 0.95)',
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
                    background: 'rgba(15, 23, 42, 0.9)',
                    border: `1px solid ${selectedLayer.color}`,
                    borderRadius: '10px',
                    padding: '1rem',
                    boxShadow: `0 4px 20px rgba(0, 0, 0, 0.4)`,
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                    <div style={{ width: '12px', height: '12px', borderRadius: '50%', background: selectedLayer.color, boxShadow: `0 0 10px ${selectedLayer.color}` }} />
                    <span style={{ fontSize: '0.72rem', fontWeight: 700, color: selectedLayer.color, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                      {selectedLayer.role}
                    </span>
                  </div>
                  <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#F8FAFC', margin: '0 0 0.5rem 0' }}>
                    {selectedLayer.title}
                  </h3>
                  <div style={{ background: 'rgba(6, 10, 23, 0.9)', padding: '0.5rem 0.75rem', borderRadius: '6px', border: '1px solid rgba(255, 255, 255, 0.08)', marginBottom: '0.75rem' }}>
                    <div style={{ fontSize: '0.65rem', color: '#64748B', marginBottom: '2px' }}>MATHEMATICAL FORMULATION:</div>
                    <code style={{ fontSize: '0.75rem', color: '#38BDF8', wordBreak: 'break-all' }}>
                      {selectedLayer.math}
                    </code>
                  </div>
                  <p style={{ fontSize: '0.78rem', color: '#CBD5E1', lineHeight: 1.5, margin: 0 }}>
                    {selectedLayer.details}
                  </p>
                </div>
              ) : (
                <div style={{ padding: '1rem', border: '1px dashed rgba(255, 255, 255, 0.15)', borderRadius: '10px', textAlign: 'center', color: '#64748B', fontSize: '0.8rem' }}>
                  Click or hover any node in the 3D model to inspect its parameters.
                </div>
              )}

              {/* Step-by-Step Transformer Pipeline */}
              {conceptType === 'neural_network' && (
                <div>
                  <h4 style={{ fontSize: '0.82rem', fontWeight: 700, color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.04em', margin: '0 0 0.65rem 0' }}>
                    Transformer Architectural Stages
                  </h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    {NEURAL_LAYERS.map((layer, idx) => (
                      <div
                        key={layer.id}
                        onClick={() => setSelectedLayer(layer)}
                        style={{
                          padding: '0.65rem 0.85rem',
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
                            width: '24px',
                            height: '24px',
                            borderRadius: '50%',
                            background: `${layer.color}25`,
                            border: `1px solid ${layer.color}`,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontSize: '0.72rem',
                            fontWeight: 700,
                            color: layer.color,
                            flexShrink: 0,
                          }}
                        >
                          {idx + 1}
                        </div>
                        <div style={{ overflow: 'hidden' }}>
                          <div style={{ fontSize: '0.75rem', fontWeight: 600, color: '#F1F5F9' }}>
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

              {/* Academic Overview Box */}
              <div
                style={{
                  marginTop: 'auto',
                  padding: '0.85rem',
                  borderRadius: '8px',
                  background: 'rgba(56, 189, 248, 0.05)',
                  border: '1px solid rgba(56, 189, 248, 0.15)',
                  fontSize: '0.72rem',
                  color: '#94A3B8',
                  lineHeight: 1.45,
                }}
              >
                🎓 <strong style={{ color: '#38BDF8' }}>Teacher Defense Note:</strong> In modern Transformers (Vaswani et al.), multi-head attention eliminates the sequential computation of RNNs/LSTMs, allowing token pairs to attend to one another in $O(1)$ sequential operations.
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
