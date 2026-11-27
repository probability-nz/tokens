// Adapted from Probability checkers, revision 204eeae6a145ba18f7c166fdcb49fd36b1700535.
import { writeFileSync } from "node:fs";
import { join } from "node:path";

// Metres, Y up. A flat underside and wide top bowl make orientation visible.
export function generateCheckers(directory) {
  const segments = 64,
    radius = 0.0195,
    height = 0.01;
  const bevel = 0.0012,
    bowlRadius = 0.0135,
    bowlDepth = 0.002;
  const rings = [];
  const add = (r, y, nr, ny) => rings.push({ r, y, nr, ny });
  add(0, 0, 0, -1);
  for (let i = 0; i <= 4; i++) {
    const a = -Math.PI / 2 + (i * Math.PI) / 8;
    add(
      radius - bevel + bevel * Math.cos(a),
      bevel + bevel * Math.sin(a),
      Math.cos(a),
      Math.sin(a),
    );
  }
  for (let i = 0; i <= 4; i++) {
    const a = (i * Math.PI) / 8;
    add(
      radius - bevel + bevel * Math.cos(a),
      height - bevel + bevel * Math.sin(a),
      Math.cos(a),
      Math.sin(a),
    );
  }
  // Contrasting 1.2 mm band around the bowl. Keep the surface at 10 mm;
  // analytic normals describe a subtle 0.12 mm embossed bead without a raised
  // collision surface or coplanar decal geometry.
  for (let i = 4; i >= 0; i--) {
    const t = i / 4;
    const slope = ((0.00012 * Math.PI) / 0.0012) * Math.sin(2 * Math.PI * t);
    const length = Math.hypot(slope, 1);
    add(bowlRadius + 0.0012 * t, height, -slope / length, 1 / length);
    rings.at(-1).band = true;
  }
  // A cosine section has a horizontal tangent at both bowl centre and lip.
  for (let i = 7; i >= 0; i--) {
    const r = (bowlRadius * i) / 8;
    const y = height - (bowlDepth * (1 + Math.cos((Math.PI * r) / bowlRadius))) / 2;
    const slope = ((bowlDepth * Math.PI) / (2 * bowlRadius)) * Math.sin((Math.PI * r) / bowlRadius);
    const length = Math.hypot(slope, 1);
    add(r, y, -slope / length, 1 / length);
  }
  const positions = [],
    normals = [],
    indices = [],
    bandIndices = [],
    starts = [];
  for (const ring of rings) {
    starts.push(positions.length / 3);
    for (let j = 0; j < (ring.r === 0 ? 1 : segments); j++) {
      const a = (j * 2 * Math.PI) / segments;
      positions.push(ring.r * Math.cos(a), ring.y, ring.r * Math.sin(a));
      normals.push(ring.nr * Math.cos(a), ring.ny, ring.nr * Math.sin(a));
    }
  }
  for (let i = 0; i < rings.length - 1; i++) {
    const target = rings[i].band && rings[i + 1].band ? bandIndices : indices;
    for (let j = 0; j < segments; j++) {
      const k = (j + 1) % segments;
      const a = starts[i] + (rings[i].r === 0 ? 0 : j);
      const b = starts[i] + (rings[i].r === 0 ? 0 : k);
      const c = starts[i + 1] + (rings[i + 1].r === 0 ? 0 : j);
      const d = starts[i + 1] + (rings[i + 1].r === 0 ? 0 : k);
      if (a !== b) target.push(a, c, b);
      if (c !== d) target.push(b, c, d);
    }
  }
  const parts = [
    new Float32Array(positions),
    new Float32Array(normals),
    new Uint16Array([...indices, ...bandIndices]),
  ];
  const buffer = Buffer.concat(parts.map((part) => Buffer.from(part.buffer)));
  writeFileSync(join(directory, "token.bin"), buffer);
  for (const colour of ["black", "white", "red"]) {
    const path = join(directory, `${colour}-token.gltf`);
    const body = {
      black: {
        name: "model:mat26.003",
        baseColorFactor: [Math.fround(0.01), Math.fround(0.01), Math.fround(0.01), 1],
      },
      white: { name: "model:mat22.004" },
      red: { name: "Lacquer red", baseColorFactor: [0.508881, 0.03434, 0.051269, 1] },
    }[colour];
    const model = {
      asset: {
        generator: "Checkers rounded token generator",
        version: "2.0",
        copyright:
          "Wood Checkboard by Jarlan Perez, CC BY 3.0. See LICENSE.md for the original source and license.",
      },
      scene: 0,
      scenes: [{ nodes: [0] }],
      nodes: [{ mesh: 0, name: `${colour} token` }],
      materials: [
        {
          doubleSided: true,
          name: body.name,
          pbrMetallicRoughness: {
            ...(body.baseColorFactor && { baseColorFactor: body.baseColorFactor }),
            metallicFactor: 0,
            roughnessFactor: Math.fround(1 - Math.sqrt(0.2)),
          },
        },
        {
          name: "Contrasting embossed dimple ring",
          pbrMetallicRoughness: {
            baseColorFactor: colour !== "white" ? [0.95, 0.95, 0.95, 1] : [0.006, 0.006, 0.006, 1],
            metallicFactor: 0,
            roughnessFactor: 0.55,
          },
        },
      ],
      meshes: [
        {
          primitives: [
            { attributes: { POSITION: 0, NORMAL: 1 }, indices: 2, material: 0 },
            { attributes: { POSITION: 0, NORMAL: 1 }, indices: 3, material: 1 },
          ],
        },
      ],
      accessors: [
        {
          bufferView: 0,
          componentType: 5126,
          count: positions.length / 3,
          min: [-radius, 0, -radius],
          max: [radius, height, radius],
          type: "VEC3",
        },
        { bufferView: 1, componentType: 5126, count: normals.length / 3, type: "VEC3" },
        { bufferView: 2, componentType: 5123, count: indices.length, type: "SCALAR" },
        {
          bufferView: 2,
          byteOffset: indices.length * 2,
          componentType: 5123,
          count: bandIndices.length,
          type: "SCALAR",
        },
      ],
      bufferViews: parts.map((part, i) => ({
        buffer: 0,
        byteOffset: parts.slice(0, i).reduce((sum, p) => sum + p.byteLength, 0),
        byteLength: part.byteLength,
        target: i === 2 ? 34963 : 34962,
      })),
      buffers: [{ byteLength: buffer.length, uri: "token.bin" }],
    };
    writeFileSync(path, JSON.stringify(model) + "\n");
  }
}
