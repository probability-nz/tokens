import type { PieceTemplate } from "../../types";

const src = "./d8/d8.gltf";

export const d8 = {
  // Asset originally created by Misha Tsyatksko for Garbo Succus
  name: "D8 Dice",
  src,
  scale: [0.016, 0.016, 0.016], //Scaled to fit inside a 16mm^3 cube
  rotation: [-54.5, 0.1, 0.1],
  faces: [
    { name: "1", rotation: [-54.5, 0.1, 0.1] },
    { name: "2", rotation: [125.5, -0.1, -0.1] },
    { name: "3", rotation: [-180, 89.8, -54.5] },
    { name: "4", rotation: [-180, 89.8, 125.5] },
    { name: "5", rotation: [125.5, -0.1, 179.9] },
    { name: "6", rotation: [-54.5, 0.1, -179.9] },
    { name: "7", rotation: [0, -89.8, -125.5] },
    { name: "8", rotation: [0, -89.8, 54.5] },
  ],
} as PieceTemplate;
