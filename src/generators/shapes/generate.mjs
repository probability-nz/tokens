// SPDX-License-Identifier: CC0-1.0
// Model dimensions are in millimetres until serialization.
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import {
  BoxGeometry,
  BufferGeometry,
  Color,
  Float32BufferAttribute,
  ShapeUtils,
  SphereGeometry,
  Vector2,
  Path,
} from "three";

const root = new URL("../../../", import.meta.url);
const assets = new URL("src/assets/cc0/", root);
const showcase = new URL("showcase/", root);
const releaseFile = new URL("release.json", showcase);
const release = JSON.parse(await readFile(releaseFile, "utf8"));
const records = new Map(release.files.map((entry) => [entry.path, entry]));
const original = await readFile(new URL("shapes/source/kenney/character.svg", assets), "utf8");
const sourcePath = /\bd="([^"]+)"/.exec(original)[1];
const credit =
  "Meeple silhouette derived from character.svg in Board Game Icons by Kenney.nl (CC0 1.0).";

// Kenney's single closed contour uses absolute moves, lines and quadratic curves.
// Repeated coordinate groups inherit their SVG command.
function meepleOutline(data) {
  const tokens = data.match(/[A-Za-z]|-?\d+(?:\.\d+)?/g);
  const path = new Path();
  let i = 0,
    command;
  const number = () => Number(tokens[i++]);
  while (i < tokens.length) {
    if (/^[A-Za-z]$/.test(tokens[i])) command = tokens[i++];
    switch (command) {
      case "M":
        path.moveTo(number(), number());
        command = "L";
        break;
      case "L":
        path.lineTo(number(), number());
        break;
      case "Q":
        path.quadraticCurveTo(number(), number(), number(), number());
        break;
      default:
        throw new Error("Unexpected SVG command " + command);
    }
  }
  // Original artwork spans 48 units. The physical piece spans 16 mm.
  const points = path.getPoints(16);
  if (points[0].equals(points.at(-1))) points.pop();
  points.forEach((p) => p.divideScalar(3));
  // Simplify arcs between the four extrema so decimation preserves tabletop size.
  const anchors = new Set([0, points.length]);
  for (const axis of ["x", "y"]) {
    for (const sign of [-1, 1]) {
      const extreme = points.reduce(
        (best, p, index) => (sign * p[axis] > sign * points[best][axis] ? index : best),
        0,
      );
      anchors.add(extreme);
    }
  }
  points.push(points[0]);
  const outline = [];
  function simplify(first, last) {
    const a = points[first],
      b = points[last];
    const segment = b.clone().sub(a);
    let split = -1,
      maxError = 0.045; // millimetres
    for (let i = first + 1; i < last; i++) {
      const delta = points[i].clone().sub(a);
      const t = Math.max(0, Math.min(1, delta.dot(segment) / segment.lengthSq()));
      const error = delta.addScaledVector(segment, -t).length();
      if (error > maxError) {
        split = i;
        maxError = error;
      }
    }
    if (split < 0) outline.push(a);
    else {
      simplify(first, split);
      simplify(split, last);
    }
  }
  const sorted = [...anchors].sort((a, b) => a - b);
  for (let i = 1; i < sorted.length; i++) simplify(sorted[i - 1], sorted[i]);
  if (ShapeUtils.isClockWise(outline)) outline.reverse();
  return outline;
}

// Extrude straight walls. The painted-wood normal texture supplies the stack
// highlight over the top 0.3 mm, exactly as on Probability's wood cutouts.
function meepleMesh() {
  const outline = meepleOutline(sourcePath);
  const count = outline.length,
    depth = 10,
    band = 0.3;
  const edges = outline.map((a, i) => {
    const b = outline[(i + 1) % count];
    return new Vector2(b.y - a.y, a.x - b.x).normalize();
  });
  const positions = [],
    normals = [],
    uvs = [],
    tangents = [],
    indices = [];
  for (const side of [false, true]) {
    for (const sign of [-1, 1]) {
      let perimeter = 0;
      for (let i = 0; i < count + (side ? 1 : 0); i++) {
        const j = i % count,
          p = outline[j],
          prev = (j + count - 1) % count;
        if (i) perimeter += p.distanceTo(outline[prev]);
        positions.push([p.x, (sign * depth) / 2, p.y]);
        if (side) {
          const n = edges[prev].clone().add(edges[j]).normalize();
          normals.push([n.x, 0, n.y]);
          tangents.push([-n.y, 0, n.x, -1]);
          // Clamp V to the neutral endpoint everywhere below the highlight.
          uvs.push([perimeter / 3.5, sign === 1 ? 1 : 1 - depth / band]);
        } else {
          normals.push([0, sign, 0]);
          tangents.push([1, 0, 0, 1]);
          uvs.push([0, 0]);
        }
      }
    }
  }
  for (const [a, b, c] of ShapeUtils.triangulateShape(outline, []))
    indices.push(a, b, c, count + a, count + c, count + b);
  const faceIndices = indices.length;
  for (let i = 0; i < count; i++) {
    const a = 2 * count + i,
      b = a + count + 1;
    indices.push(a, b, b + 1, a, b + 1, a + 1);
  }
  const mesh = indexed(positions, indices, normals);
  mesh.setAttribute("uv", new Float32BufferAttribute(uvs.flat(), 2));
  mesh.setAttribute("tangent", new Float32BufferAttribute(tangents.flat(), 4));
  mesh.addGroup(0, faceIndices, 0);
  mesh.addGroup(faceIndices, indices.length - faceIndices, 1);
  return mesh;
}

async function publish(path, data, mediaType) {
  const bytes = Buffer.from(data);
  await writeFile(new URL(path, showcase), bytes);
  records.set(path, {
    path,
    mediaType,
    bytes: bytes.length,
    sha256: createHash("sha256").update(bytes).digest("hex"),
  });
}

function indexed(points, indices, normals) {
  const mesh = new BufferGeometry();
  mesh.setAttribute("position", new Float32BufferAttribute(points.flat(), 3));
  mesh.setIndex(indices);
  if (normals) mesh.setAttribute("normal", new Float32BufferAttribute(normals.flat(), 3));
  else mesh.computeVertexNormals();
  return mesh;
}

// Give each face its own vertices to keep edges sharp. The top and bottom
// polygons use ear clipping so the same extrusion works for the concave meeple.
function prism(profile, depth, smoothAt = () => false) {
  const contour = profile.map(([x, z]) => new Vector2(x, z));
  if (ShapeUtils.isClockWise(contour)) contour.reverse();
  const triangles = ShapeUtils.triangulateShape(contour, []);
  const points = [],
    indices = [];
  for (const sign of [-1, 1]) {
    const offset = points.length;
    for (const { x, y: z } of contour) points.push([x, (sign * depth) / 2, z]);
    for (const [a, b, c] of triangles) {
      indices.push(offset + a, offset + (sign < 0 ? b : c), offset + (sign < 0 ? c : b));
    }
  }
  const capVertices = points.length;
  const edges = contour.map((a, i) => {
    const b = contour[(i + 1) % contour.length];
    return new Vector2(b.y - a.y, a.x - b.x).normalize();
  });
  for (const [i, a] of contour.entries()) {
    const b = contour[(i + 1) % contour.length];
    const start = points.length;
    for (const [v, y] of [
      [a, -depth / 2],
      [a, depth / 2],
      [b, depth / 2],
      [b, -depth / 2],
    ]) {
      points.push([v.x, y, v.y]);
    }
    indices.push(start, start + 1, start + 2, start, start + 2, start + 3);
  }
  const mesh = indexed(points, indices);
  const normals = mesh.getAttribute("normal");
  for (const i of edges.keys()) {
    const next = (i + 1) % edges.length;
    for (const [corner, point] of [i, i, next, next].entries()) {
      if (!smoothAt(contour[point])) continue;
      const previous = (point + edges.length - 1) % edges.length;
      const n = edges[previous].clone().add(edges[point]).normalize();
      normals.setXYZ(capVertices + 4 * i + corner, n.x, 0, n.y);
    }
  }
  return mesh;
}

function goStone() {
  // Revolve the superellipse r^p + |y|^p = 1. Its gradient gives the normal.
  const exponent = 1.6,
    radius = 11,
    halfHeight = 4.25;
  const rings = [-2 / 3, -1 / 4, 0, 1 / 4, 2 / 3];
  const points = [],
    normals = [],
    indices = [];
  const segments = 24;
  for (const y of rings) {
    const r = (1 - Math.abs(y) ** exponent) ** (1 / exponent);
    const radial = r ** (exponent - 1) / radius;
    const vertical = (Math.sign(y) * Math.abs(y) ** (exponent - 1)) / halfHeight;
    const length = Math.hypot(radial, vertical);
    for (let i = 0; i < segments; i++) {
      const angle = (2 * Math.PI * i) / segments;
      const x = Math.cos(angle),
        z = Math.sin(angle);
      points.push([radius * r * x, halfHeight * (1 + y), radius * r * z]);
      normals.push([(radial * x) / length, vertical / length, (radial * z) / length]);
    }
  }
  const bottom = points.length,
    top = bottom + 1;
  points.push([0, 0, 0], [0, 8.5, 0]);
  normals.push([0, -1, 0], [0, 1, 0]);
  for (let i = 0; i < segments; i++) {
    const next = (i + 1) % segments;
    indices.push(bottom, i, next);
    for (let r = 0; r < rings.length - 1; r++) {
      const a = r * segments + i,
        b = r * segments + next;
      indices.push(a, a + segments, b + segments, a, b + segments, b);
    }
    const last = (rings.length - 1) * segments;
    indices.push(top, last + next, last + i);
  }
  return indexed(points, indices, normals);
}

async function writeModel(family, slug, name, mesh, color, roughnessFactor, bufferName = slug) {
  const dir = new URL(family + "/", assets);
  await mkdir(dir, { recursive: true });
  const positions = mesh.getAttribute("position").clone();
  for (let i = 0; i < positions.array.length; i++) positions.array[i] /= 1000;
  const bounds = new BufferGeometry().setAttribute("position", positions);
  bounds.computeBoundingBox();
  const chunks = [],
    bufferViews = [],
    accessors = [];
  let byteLength = 0;
  const attributes = [positions, mesh.getAttribute("normal")];
  if (mesh.hasAttribute("tangent"))
    attributes.push(mesh.getAttribute("uv"), mesh.getAttribute("tangent"));
  const indexAccessor = attributes.length;
  attributes.push(mesh.index);
  for (const attribute of attributes) {
    const index = attribute === mesh.index;
    const { array } = attribute;
    const chunk = Buffer.from(array.buffer, array.byteOffset, array.byteLength);
    chunks.push(chunk);
    accessors.push({
      bufferView: bufferViews.length,
      componentType: index ? 5123 : 5126,
      count: attribute.count,
      type: index ? "SCALAR" : "VEC" + attribute.itemSize,
    });
    bufferViews.push({
      buffer: 0,
      byteOffset: byteLength,
      byteLength: chunk.length,
      target: index ? 34963 : 34962,
    });
    byteLength += chunk.length;
  }
  Object.assign(accessors[0], {
    min: bounds.boundingBox.min.toArray(),
    max: bounds.boundingBox.max.toArray(),
  });
  const uri = bufferName + ".bin";
  const material = {
    pbrMetallicRoughness: { baseColorFactor: color, metallicFactor: 0, roughnessFactor },
  };
  if (color[3] < 1) material.alphaMode = "BLEND";
  const gltf = {
    asset: { version: "2.0", generator: "tokens generate:shapes", copyright: "CC0-1.0" },
    scene: 0,
    scenes: [{ nodes: [0] }],
    nodes: [{ name, mesh: 0 }],
    meshes: [
      {
        primitives: [
          { attributes: { POSITION: 0, NORMAL: 1 }, indices: indexAccessor, material: 0 },
        ],
      },
    ],
    materials: [material],
    buffers: [{ uri, byteLength }],
    bufferViews,
    accessors,
  };
  const binary = Buffer.concat(chunks);
  if (slug === "meeple") {
    gltf.asset.copyright = credit;
    const image = "wood-top-edge-normal.png";
    await publish("cc0/shapes/" + image, await readFile(new URL(image, dir)), "image/png");
    gltf.images = [{ uri: image, mimeType: "image/png" }];
    gltf.textures = [{ source: 0, sampler: 0 }];
    gltf.samplers = [{ magFilter: 9729, minFilter: 9729, wrapS: 10497, wrapT: 33071 }];
    gltf.materials.push({ ...material, normalTexture: { index: 0, scale: 0.7 } });
    const fullIndex = accessors[indexAccessor];
    gltf.meshes[0].primitives = mesh.groups.map(({ start, count, materialIndex }) => {
      const view = { ...fullIndex, byteOffset: start * 2, count };
      const indices = start === 0 ? indexAccessor : accessors.length;
      accessors[indices] = view;
      const attributes = { POSITION: 0, NORMAL: 1 };
      if (materialIndex === 1) Object.assign(attributes, { TEXCOORD_0: 2, TANGENT: 3 });
      return { attributes, indices, material: materialIndex };
    });
  }
  const json = JSON.stringify(gltf) + "\n";
  const showcaseFamily = ["cube", "sphere"].includes(slug) ? "showcase/shapes" : "cc0/" + family;
  await writeFile(new URL(uri, dir), binary);
  await publish(showcaseFamily + "/" + uri, binary, "application/octet-stream");
  await writeFile(new URL(slug + ".gltf", dir), json);
  await publish(showcaseFamily + "/" + slug + ".gltf", json, "model/gltf+json");
}

function polygon(sides, radius, phase = 0) {
  return Array.from({ length: sides }, (_, i) => {
    const angle = phase + (i * 2 * Math.PI) / sides;
    return [radius * Math.cos(angle), radius * Math.sin(angle)];
  });
}

// Split a square along a diagonal, or add a triangular roof above its walls.
const square = polygon(4, 25 * Math.SQRT2, Math.PI / 4).map((p) => p.map(Math.round));
const triangle = polygon(3, 1, -Math.PI / 2).map(([x, y]) => [
  (50 * x) / Math.sqrt(3),
  (43 * (y + 1)) / 1.5 - 21.5,
]);
const houseWidth = 40,
  houseHeight = 53;
const wallHeight = (houseHeight * 5) / 8;
const house = square.map(([x, z]) => [
  (x / 50) * houseWidth,
  houseHeight / 2 - (z < 0 ? wallHeight : 0),
]);
house.splice(3, 0, [0, -houseHeight / 2]);
const circle = polygon(36, 25);
function squarePyramid() {
  const points = square.map(([x, z]) => [x, -21.5, z]);
  const indices = [0, 1, 2, 0, 2, 3];
  for (let i = 0; i < 4; i++) {
    const start = points.length;
    points.push(points[(i + 1) % 4], points[i], [0, 21.5, 0]);
    indices.push(start, start + 1, start + 2);
  }
  return indexed(points, indices);
}
const rgb = (hex) => [...new Color(hex).toArray(), 1];
const shapes = [
  ["cube", "Cube", new BoxGeometry(50, 50, 50).translate(0, 25, 0), [0, 1, 0, 1], 0.55],
  ["sphere", "Sphere", new SphereGeometry(25, 20, 12).translate(0, 25, 0), [1, 0, 1, 1], 0.55],
  ["cylinder", "Cylinder", prism(circle, 50, () => true), [1, 0, 0, 1], 0.54],
  ["pyramid", "Pyramid", squarePyramid(), [1, 0.21586, 0, 1], 0.55],
  ["house", "House", prism(house, 40), rgb("#408080"), 0.54],
  ["triangular-prism", "Triangular-Prism", prism(triangle, 50), rgb("#00ff80"), 0.54],
  [
    "right-angle-prism",
    "Right-Angle-Prism",
    prism([square[0], square[1], square[3]], 50),
    [0, 1, 1, 1],
    0.54,
  ],
  ["meeple", "G10", meepleMesh(), rgb("#467c89"), 0.54],
];
for (const args of shapes) await writeModel("shapes", ...args);
const stone = goStone();
await writeModel(
  "stones",
  "stone-black",
  "Stone Black",
  stone,
  [0.018, 0.023, 0.028, 0.9],
  0.25,
  "stone",
);
await writeModel(
  "stones",
  "stone-white",
  "Stone White",
  stone,
  [0.8, 0.775, 0.718, 0.9],
  0.3,
  "stone",
);

const preview =
  '<svg xmlns="http://www.w3.org/2000/svg" width="16mm" height="16mm" viewBox="-24 -24 48 48"><title>' +
  credit +
  '</title><path fill="#467c89" d="' +
  sourcePath +
  '"/></svg>\n';
await writeFile(new URL("shapes/source/meeple.svg", assets), preview);
release.files = [...records.values()].sort((a, b) =>
  a.path < b.path ? -1 : a.path > b.path ? 1 : 0,
);
await writeFile(releaseFile, JSON.stringify(release, null, 2) + "\n");
