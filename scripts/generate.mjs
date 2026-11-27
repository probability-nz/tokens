// Each authoring backend runs in isolation. Families share the showcase manifest,
// so complete one publisher before starting the next.
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const families = {
  dice: ["src/generators/dice/generate.mjs"],
  shapes: ["src/generators/shapes/generate.mjs"],
  boards: ["src/generators/tabletop/generate.mjs", "boards"],
  dominoes: ["src/generators/tabletop/generate.mjs", "dominoes"],
  "poker-chips": ["src/generators/tabletop/generate.mjs", "poker-chips"],
  checkers: ["src/generators/tabletop/generate.mjs", "checkers"],
  classic: ["src/generators/classic/generate.mjs"],
};
const [family = "all"] = process.argv.slice(2);
if (family === "--help" || family === "-h") {
  console.log("pnpm generate [all | " + Object.keys(families).join(" | ") + "]");
} else {
  if (family !== "all" && !Object.hasOwn(families, family))
    throw Error("Unknown family: " + family);
  const run = (args) => execFileSync(process.execPath, args, { cwd: root, stdio: "inherit" });
  for (const key of family === "all" ? Object.keys(families) : [family]) {
    console.log("Generating " + key);
    run(families[key]);
  }
  run(["scripts/optimize.mjs"]);
}
