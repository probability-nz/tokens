import type { PieceTemplate } from "../../types";

const src = "./d20/d20.gltf";

export const d20 = {
  // Asset originally created by Misha Tsyatsko for Garbo Succus
  name: "D20 Dice",
  src,
  scale: [0.016, 0.016, 0.016], //Scaled to fit inside a 16mm^3 cube
  rotation: [-100.8, -90, 0],
  faces: [
    { name: "1", rotation: [-100.8, -90, 0] },
    { name: "2", rotation: [41.8, 30, -37.4] },
    { name: "3", rotation: [79.2, -18, 0] },
    { name: "4", rotation: [-159.1, 0, -148.3] },
    { name: "5", rotation: [-37.4, 18, 0] },
    { name: "6", rotation: [79.2, 54, 0] },
    { name: "7", rotation: [-37.4, 90, 0] },
    { name: "8", rotation: [20.9, 0, 31.7] },
    { name: "9", rotation: [79.2, -18, 180] },
    { name: "10", rotation: [-37.4, -18, 63.4] },
    { name: "11", rotation: [142.6, -18, 63.4] },
    { name: "12", rotation: [-37.4, 18, -180] },
    { name: "13", rotation: [142.6, 90, 0] },
    { name: "14", rotation: [-138.2, -30, 100.8] },
    { name: "15", rotation: [-100.8, -18, 180] },
    { name: "16", rotation: [20.9, 0, -148.3] },
    { name: "17", rotation: [-100.8, 18, -116.6] },
    { name: "18", rotation: [-37.4, -54, 180] },
    { name: "19", rotation: [142.6, 18, 0] },
    { name: "20", rotation: [79.2, -90, 0] },
  ],
} as PieceTemplate;
