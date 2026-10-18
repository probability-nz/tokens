import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const names = ['die', 'd4', 'd6', 'd8', 'd12', 'd20'];

type LinkedViews = { controls: Set<OrbitControls>; syncing: boolean };

function Die({ name, linked }: { name: string; linked: LinkedViews }) {
  const host = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const element = host.current!;
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    renderer.setClearColor(0xeeeeee, 1);
    element.append(renderer.domElement);
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(35, 1, 0.01, 100);
    camera.position.set(3, 2.5, 3);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enablePan = false;
    controls.minDistance = 2;
    controls.maxDistance = 10;
    scene.add(new THREE.AmbientLight(0xffffff, 1.5));
    const light = new THREE.DirectionalLight(0xffffff, 3);
    light.position.set(3, 5, 2);
    scene.add(light);
    const render = () => renderer.render(scene, camera);
    const copyView = (source: OrbitControls, target: OrbitControls) => {
      target.object.position.copy(source.object.position);
      target.object.up.copy(source.object.up);
      target.target.copy(source.target);
      target.update();
    };
    const existing = linked.controls.values().next().value;
    if (existing) {
      copyView(existing, controls);
    }
    linked.controls.add(controls);
    const onChange = () => {
      render();
      if (linked.syncing) {
        return;
      }
      linked.syncing = true;
      try {
        for (const other of linked.controls) {
          if (other !== controls) {
            copyView(controls, other);
          }
        }
      } finally {
        linked.syncing = false;
      }
    };
    controls.addEventListener('change', onChange);
    const resize = new ResizeObserver(() => {
      renderer.setSize(element.clientWidth, 280);
      camera.aspect = element.clientWidth / 280;
      camera.updateProjectionMatrix();
      render();
    });
    resize.observe(element);
    let disposed = false;
    let model: THREE.Group | undefined;
    const release = (object: THREE.Object3D) =>
      object.traverse((child) => {
        if (!(child instanceof THREE.Mesh)) {
          return;
        }
        child.geometry.dispose();
        const materials = Array.isArray(child.material)
          ? child.material
          : [child.material];
        for (const material of materials) {
          for (const value of Object.values(material)) {
            if (value instanceof THREE.Texture) {
              value.dispose();
            }
          }
          material.dispose();
        }
      });
    new GLTFLoader().load(
      `/blank-dice/${name}-blank.gltf`,
      (gltf) => {
        if (disposed) {
          release(gltf.scene);
          return;
        }
        model = gltf.scene;
        const bounds = new THREE.Box3().setFromObject(model);
        const centre = bounds.getCenter(new THREE.Vector3());
        model.position.sub(centre);
        scene.add(model);
        controls.update();
        render();
        element.dataset.loaded = 'true';
      },
      undefined,
      (error) => {
        if (!disposed) {
          element.textContent = `Unable to load ${name}`;
          console.error(error);
        }
      },
    );
    return () => {
      disposed = true;
      resize.disconnect();
      linked.controls.delete(controls);
      controls.removeEventListener('change', onChange);
      controls.dispose();
      if (model) {
        release(model);
      }
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, [name, linked]);
  return (
    <div
      ref={host}
      aria-label={`Blank ${name}`}
      style={{ minWidth: 0, height: 280 }}
    />
  );
}

export function BlankDicePreview() {
  const [linked] = useState<LinkedViews>(() => ({
    controls: new Set(),
    syncing: false,
  }));
  return (
    <div
      style={{
        background: '#eee',
        minHeight: '100vh',
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
        alignContent: 'start',
      }}
    >
      {names.map((name) => (
        <Die key={name} name={name} linked={linked} />
      ))}
    </div>
  );
}
