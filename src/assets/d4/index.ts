import type { PieceTemplate } from "../../types";

const src = "./d4/d4.gltf";

export const d4 = {
  // Asset originally created by Misha Tsyatksko for Garbo Succus
  name: "D4 Dice",
  src,
  scale: [0.016, 0.016, 0.016],    //Scaled to fit inside a 16mm^3 cube
  rotation: [0, 0, 0],
  faces: [
    { name: "1", rotation: [0, 0, 0] },
    { name: "2", rotation: [-29.8, 17.2, 120.7] },
    { name: "3", rotation: [-144.7, -34.8, 90.9] },
    { name: "4", rotation: [99.4, 15.9, 58.7] },
  ],
} as PieceTemplate;
