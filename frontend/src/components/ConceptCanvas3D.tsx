import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';

export interface Concept3DProps {
  conceptType: 'neural_network' | 'distributed_cluster' | 'molecule' | 'quantum_bloch' | 'generic';
  title?: string;
  description?: string;
}

export const ConceptCanvas3D: React.FC<Concept3DProps> = ({
  conceptType = 'neural_network',
  title,
  description,
}) => {
  const mountRef = useRef<HTMLDivElement>(null);
  const [activeNodeInfo, setActiveNodeInfo] = useState<string | null>(null);
  const [isRotating, setIsRotating] = useState<boolean>(true);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    // Dimensions
    const width = mount.clientWidth || 400;
    const height = 280;

    // 1. Scene, Camera, Renderer
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a101f); // Midnight Oxford Navy

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    camera.position.set(0, 0, 18);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    mount.appendChild(renderer.domElement);

    // 2. Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.8);
    scene.add(ambientLight);

    const pointLight = new THREE.PointLight(0x38bdf8, 2, 50); // Cyan glow
    pointLight.position.set(10, 10, 10);
    scene.add(pointLight);

    const purpleLight = new THREE.PointLight(0xa855f7, 1.5, 50); // Violet rim light
    purpleLight.position.set(-10, -10, -10);
    scene.add(purpleLight);

    // Group for all interactive geometries
    const mainGroup = new THREE.Group();
    scene.add(mainGroup);

    const interactiveObjects: THREE.Object3D[] = [];

    // 3. Build Concept-Specific Geometry
    if (conceptType === 'neural_network') {
      // 3D Multi-Layer Perceptron (Input, 2 Hidden, Output)
      const layers = [3, 4, 4, 2];
      const layerSpacing = 3.5;
      const nodeSpacing = 2.0;
      const nodePositions: THREE.Vector3[][] = [];

      const nodeGeo = new THREE.SphereGeometry(0.35, 16, 16);
      const inputMat = new THREE.MeshPhongMaterial({ color: 0x38bdf8, emissive: 0x0284c7, shininess: 80 });
      const hiddenMat = new THREE.MeshPhongMaterial({ color: 0xa855f7, emissive: 0x7e22ce, shininess: 80 });
      const outputMat = new THREE.MeshPhongMaterial({ color: 0x22c55e, emissive: 0x15803d, shininess: 80 });

      layers.forEach((count, lIdx) => {
        const layerNodes: THREE.Vector3[] = [];
        const x = (lIdx - (layers.length - 1) / 2) * layerSpacing;
        const mat = lIdx === 0 ? inputMat : lIdx === layers.length - 1 ? outputMat : hiddenMat;

        for (let i = 0; i < count; i++) {
          const y = (i - (count - 1) / 2) * nodeSpacing;
          const pos = new THREE.Vector3(x, y, 0);
          layerNodes.push(pos);

          const mesh = new THREE.Mesh(nodeGeo, mat);
          mesh.position.copy(pos);
          const typeName = lIdx === 0 ? 'Input Feature' : lIdx === layers.length - 1 ? 'Output Logit' : 'Hidden ReLU Neuron';
          mesh.userData = { label: `${typeName} [L${lIdx}, N${i + 1}]` };
          mainGroup.add(mesh);
          interactiveObjects.push(mesh);
        }
        nodePositions.push(layerNodes);
      });

      // Synapse Connections (Cylinders)
      const lineMat = new THREE.LineBasicMaterial({ color: 0x334155, transparent: true, opacity: 0.5 });
      for (let l = 0; l < nodePositions.length - 1; l++) {
        for (const p1 of nodePositions[l]) {
          for (const p2 of nodePositions[l + 1]) {
            const points = [p1, p2];
            const geo = new THREE.BufferGeometry().setFromPoints(points);
            const line = new THREE.Line(geo, lineMat);
            mainGroup.add(line);
          }
        }
      }
    } else if (conceptType === 'distributed_cluster') {
      // 3D Raft Distributed Consensus Cluster
      // Center: Gold Leader Node
      const leaderGeo = new THREE.SphereGeometry(0.7, 24, 24);
      const leaderMat = new THREE.MeshPhongMaterial({ color: 0xf59e0b, emissive: 0xb45309, shininess: 100 });
      const leader = new THREE.Mesh(leaderGeo, leaderMat);
      leader.userData = { label: 'Raft Leader Node (Active Term 4)' };
      mainGroup.add(leader);
      interactiveObjects.push(leader);

      // Orbital Follower Nodes
      const followerCount = 5;
      const radius = 4.5;
      const followerGeo = new THREE.SphereGeometry(0.45, 16, 16);
      const followerMat = new THREE.MeshPhongMaterial({ color: 0x38bdf8, emissive: 0x0284c7, shininess: 70 });

      for (let i = 0; i < followerCount; i++) {
        const angle = (i / followerCount) * Math.PI * 2;
        const fx = Math.cos(angle) * radius;
        const fy = Math.sin(angle) * radius * 0.7;
        const fz = Math.sin(angle) * 1.5;

        const follower = new THREE.Mesh(followerGeo, followerMat);
        follower.position.set(fx, fy, fz);
        follower.userData = { label: `Follower Node #${i + 1} (Heartbeat OK)` };
        mainGroup.add(follower);
        interactiveObjects.push(follower);

        // Heartbeat connection beam
        const pts = [new THREE.Vector3(0, 0, 0), new THREE.Vector3(fx, fy, fz)];
        const lineGeo = new THREE.BufferGeometry().setFromPoints(pts);
        const lineMat = new THREE.LineBasicMaterial({ color: 0x0ea5e9, transparent: true, opacity: 0.6 });
        const beam = new THREE.Line(lineGeo, lineMat);
        mainGroup.add(beam);
      }
    } else if (conceptType === 'quantum_bloch') {
      // 3D Quantum Bloch Sphere
      const sphereGeo = new THREE.SphereGeometry(4, 24, 24);
      const wireMat = new THREE.MeshBasicMaterial({ color: 0x38bdf8, wireframe: true, transparent: true, opacity: 0.25 });
      const sphere = new THREE.Mesh(sphereGeo, wireMat);
      mainGroup.add(sphere);

      // Axes: X, Y, Z
      const axesHelper = new THREE.AxesHelper(5.5);
      mainGroup.add(axesHelper);

      // Quantum State Vector |psi>
      const dir = new THREE.Vector3(1, 1, 1).normalize();
      const origin = new THREE.Vector3(0, 0, 0);
      const arrowHelper = new THREE.ArrowHelper(dir, origin, 4.2, 0xef4444, 0.6, 0.3);
      arrowHelper.userData = { label: 'Quantum State Vector |ψ⟩ = α|0⟩ + β|1⟩' };
      mainGroup.add(arrowHelper);

      // North Pole |0> and South Pole |1>
      const poleGeo = new THREE.SphereGeometry(0.3, 16, 16);
      const northMat = new THREE.MeshPhongMaterial({ color: 0x22c55e });
      const north = new THREE.Mesh(poleGeo, northMat);
      north.position.set(0, 4, 0);
      north.userData = { label: 'Basis State |0⟩ (North Pole)' };
      mainGroup.add(north);
      interactiveObjects.push(north);

      const southMat = new THREE.MeshPhongMaterial({ color: 0xa855f7 });
      const south = new THREE.Mesh(poleGeo, southMat);
      south.position.set(0, -4, 0);
      south.userData = { label: 'Basis State |1⟩ (South Pole)' };
      mainGroup.add(south);
      interactiveObjects.push(south);
    } else {
      // Molecule: Benzene Ring (C6H6)
      const ringRadius = 3.5;
      const carbonGeo = new THREE.SphereGeometry(0.5, 16, 16);
      const carbonMat = new THREE.MeshPhongMaterial({ color: 0x64748b, emissive: 0x334155, shininess: 60 });
      const hydrogenGeo = new THREE.SphereGeometry(0.25, 16, 16);
      const hydrogenMat = new THREE.MeshPhongMaterial({ color: 0xf1f5f9, shininess: 90 });

      for (let i = 0; i < 6; i++) {
        const angle = (i / 6) * Math.PI * 2;
        const cx = Math.cos(angle) * ringRadius;
        const cy = Math.sin(angle) * ringRadius;

        const cMesh = new THREE.Mesh(carbonGeo, carbonMat);
        cMesh.position.set(cx, cy, 0);
        cMesh.userData = { label: `Carbon Atom C-${i + 1} (sp² hybridized)` };
        mainGroup.add(cMesh);
        interactiveObjects.push(cMesh);

        // Hydrogen attached
        const hx = Math.cos(angle) * (ringRadius + 1.8);
        const hy = Math.sin(angle) * (ringRadius + 1.8);
        const hMesh = new THREE.Mesh(hydrogenGeo, hydrogenMat);
        hMesh.position.set(hx, hy, 0);
        hMesh.userData = { label: `Hydrogen Atom H-${i + 1}` };
        mainGroup.add(hMesh);
        interactiveObjects.push(hMesh);

        // Bond lines
        const nextAngle = ((i + 1) / 6) * Math.PI * 2;
        const ncx = Math.cos(nextAngle) * ringRadius;
        const ncy = Math.sin(nextAngle) * ringRadius;
        const bondGeo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(cx, cy, 0), new THREE.Vector3(ncx, ncy, 0)]);
        const bondLine = new THREE.Line(bondGeo, new THREE.LineBasicMaterial({ color: 0x94a3b8 }));
        mainGroup.add(bondLine);

        const chBondGeo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(cx, cy, 0), new THREE.Vector3(hx, hy, 0)]);
        const chBondLine = new THREE.Line(chBondGeo, new THREE.LineBasicMaterial({ color: 0xcfd8dc }));
        mainGroup.add(chBondLine);
      }
    }

    // 4. Mouse Drag & Orbit Interaction
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

      // Raycast for hover tooltips
      const rect = renderer.domElement.getBoundingClientRect();
      const mouse = new THREE.Vector2(
        ((e.clientX - rect.left) / rect.width) * 2 - 1,
        -((e.clientY - rect.top) / rect.height) * 2 + 1
      );

      const raycaster = new THREE.Raycaster();
      raycaster.setFromCamera(mouse, camera);
      const intersects = raycaster.intersectObjects(interactiveObjects, true);

      if (intersects.length > 0 && intersects[0].object.userData?.label) {
        setActiveNodeInfo(intersects[0].object.userData.label);
      } else if (!isDragging) {
        setActiveNodeInfo(null);
      }
    };

    const onMouseUp = () => {
      isDragging = false;
    };

    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      camera.position.z = Math.max(8, Math.min(30, camera.position.z + e.deltaY * 0.02));
    };

    const dom = renderer.domElement;
    dom.addEventListener('mousedown', onMouseDown);
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    dom.addEventListener('wheel', onWheel, { passive: false });

    // 5. Animation Loop
    let animId: number;
    const animate = () => {
      animId = requestAnimationFrame(animate);
      if (isRotating && !isDragging) {
        mainGroup.rotation.y += 0.006;
      }
      renderer.render(scene, camera);
    };
    animate();

    // 6. Cleanup
    return () => {
      cancelAnimationFrame(animId);
      dom.removeEventListener('mousedown', onMouseDown);
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
      dom.removeEventListener('wheel', onWheel);
      if (mount && dom.parentElement === mount) {
        mount.removeChild(dom);
      }
      renderer.dispose();
    };
  }, [conceptType, isRotating]);

  return (
    <div
      style={{
        borderRadius: '10px',
        overflow: 'hidden',
        border: '1px solid rgba(56, 189, 248, 0.25)',
        background: '#070D1B',
        marginTop: '0.6rem',
        marginBottom: '0.6rem',
        boxShadow: '0 8px 24px rgba(0, 0, 0, 0.4)',
      }}
    >
      {/* Header Bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0.45rem 0.75rem',
          background: 'linear-gradient(90deg, rgba(14, 22, 38, 0.95), rgba(8, 13, 26, 0.95))',
          borderBottom: '1px solid rgba(56, 189, 248, 0.15)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <span style={{ fontSize: '0.9rem' }}>🪐</span>
          <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#38BDF8', letterSpacing: '0.04em', textTransform: 'uppercase' }}>
            {title || `Interactive 3D WebGL Concept: ${conceptType.replace('_', ' ')}`}
          </span>
        </div>
        <div style={{ display: 'flex', gap: '0.35rem' }}>
          <button
            type="button"
            onClick={() => setIsRotating((prev) => !prev)}
            style={{
              fontSize: '0.65rem',
              padding: '0.15rem 0.45rem',
              borderRadius: '4px',
              border: '1px solid rgba(255, 255, 255, 0.15)',
              background: isRotating ? 'rgba(56, 189, 248, 0.15)' : 'transparent',
              color: isRotating ? '#38BDF8' : '#94A3B8',
              cursor: 'pointer',
            }}
          >
            {isRotating ? 'Auto-Rotate ON' : 'Paused'}
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
        {/* Overlay Instructions & Live Inspection Label */}
        <div
          style={{
            position: 'absolute',
            bottom: '8px',
            left: '8px',
            right: '8px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            pointerEvents: 'none',
          }}
        >
          <span style={{ fontSize: '0.65rem', color: '#64748B', background: 'rgba(0,0,0,0.6)', padding: '2px 6px', borderRadius: '4px' }}>
            🖱️ Drag to rotate • Scroll to zoom
          </span>
          {activeNodeInfo && (
            <span
              style={{
                fontSize: '0.7rem',
                fontWeight: 600,
                color: '#38BDF8',
                background: 'rgba(15, 23, 42, 0.9)',
                border: '1px solid #38BDF8',
                padding: '2px 8px',
                borderRadius: '4px',
                animation: 'fadeIn 0.2s ease-in',
              }}
            >
              🎯 {activeNodeInfo}
            </span>
          )}
        </div>
      </div>

      {description && (
        <div
          style={{
            padding: '0.4rem 0.75rem',
            fontSize: '0.72rem',
            color: '#94A3B8',
            background: 'rgba(10, 16, 31, 0.8)',
            borderTop: '1px solid rgba(255, 255, 255, 0.05)',
            lineHeight: 1.4,
          }}
        >
          {description}
        </div>
      )}
    </div>
  );
};
