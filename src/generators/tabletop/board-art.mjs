// SPDX-License-Identifier: CC0-1.0
import settings from "../texture-settings.json" with { type: "json" };
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { copyFile, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";

// The editable SVGs are the masters. Reuse the published board solids.
export async function generateBoardArt(source, output, scratch) {
  for (const name of ["go", "nine-mens-morris", "backgammon"]) {
    const modelFile = name + ".gltf";
    const model = JSON.parse(await readFile(join(source, modelFile)));
    const png = join(scratch, name + ".png");
    const avif = join(scratch, name + ".avif");
    execFileSync(
      "inkscape",
      [join(source, "source", name + ".svg"), "--export-width=3072", "--export-filename=" + png],
      { stdio: "inherit" },
    );
    execFileSync(
      "magick",
      [
        "-limit",
        "thread",
        "1",
        png,
        "-strip",
        "-define",
        "heic:speed=6",
        "-define",
        "heic:chroma=444",
        "-quality",
        String(settings.avifQuality),
        avif,
      ],
      { stdio: "inherit" },
    );
    const bytes = await readFile(avif);
    const uri = createHash("sha256").update(bytes).digest("hex").slice(0, 20) + ".avif";
    model.images[0].uri = uri;
    for (const buffer of model.buffers) {
      if (buffer.uri) await copyFile(join(source, buffer.uri), join(output, buffer.uri));
    }
    await writeFile(join(output, uri), bytes);
    await writeFile(join(output, modelFile), JSON.stringify(model) + "\n");
  }
}
