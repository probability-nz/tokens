import type { PieceTemplate } from "../../types";

const src = "./d12/d12.gltf";

export const d12 = {
  // Asset originally created by Misha Tsyatksko for Garbo Succus
  name: "D12 Dice",
  src,
  scale: [0.016, 0.016, 0.016], //Scaled to fit inside a 16mm^3 cube
  rotation: [100.7, -30, 20.8], // Default rotation: face 1 up
  faces: [
    { name: "1", rotation: [100.7, -30, 20.8] },
    { name: "2", rotation: [100.7, 30, -20.6] },
    { name: "3", rotation: [0, 54.8, -58.3] },
    { name: "4", rotation: [31.7, -0.4, 0.2] },
    { name: "5", rotation: [180, 54.1, -121.7] },
    { name: "6", rotation: [-148.3, -0.2, -179.9] },
    { name: "7", rotation: [-81.4, 30.6, -16.6] },
    { name: "8", rotation: [-79.2, -30, 20.9] },
    { name: "9", rotation: [0, 52.2, -121.7] },
    { name: "10", rotation: [-148.3, -1.9, 1.2] },
    { name: "11", rotation: [0, -89.7, 121.7] },
    { name: "12", rotation: [31.7, 1.3, 179.2] },
  ],
} as PieceTemplate;
