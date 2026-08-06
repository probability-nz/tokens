type Resource = { uri?: string };
type Texture = {
  extensions?: Record<string, unknown>;
};
type Gltf = {
  buffers?: Resource[];
  images?: Resource[];
  textures?: Texture[];
};

const sources = new Map<string, Promise<string>>();

const loadPreferredSource = async (src: string): Promise<string> => {
  const response = await fetch(src);
  if (!response.ok) throw new Error(`${src} returned ${response.status}`);
  const gltf = (await response.json()) as Gltf;
  for (const resource of [...(gltf.buffers ?? []), ...(gltf.images ?? [])]) {
    if (resource.uri !== undefined && !resource.uri.startsWith('data:')) {
      resource.uri = new URL(resource.uri, response.url).href;
    }
  }
  for (const texture of gltf.textures ?? []) {
    if (texture.extensions?.EXT_texture_avif !== undefined) {
      delete texture.extensions.EXT_texture_webp;
    }
  }
  return `data:model/gltf+json,${encodeURIComponent(JSON.stringify(gltf))}`;
};

export const preferredGltfSource = (src: string): Promise<string> => {
  const existing = sources.get(src);
  if (existing !== undefined) return existing;
  const source = loadPreferredSource(src);
  sources.set(src, source);
  return source;
};
