import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
import { ImageLoader, LoadingManager, Texture, TextureLoader } from 'three';

// Each glTF parser configures its own sampler. Sharing the Source lets Three
// reuse both the decoded image and the GPU allocation for matching samplers.
export class SharedTextureLoader extends TextureLoader {
  private images = new Map<string, { texture: Texture<HTMLImageElement>; ready: Promise<HTMLImageElement> }>();

  override load(url: string, onLoad?: (texture: Texture<HTMLImageElement>) => void,
    _onProgress?: (event: ProgressEvent) => void, onError?: (error: unknown) => void) {
    let image = this.images.get(url);
    if (!image) {
      const texture = new Texture<HTMLImageElement>();
      const ready = new ImageLoader(this.manager).setCrossOrigin(this.crossOrigin).loadAsync(url)
        .then((element) => {
          texture.image = element;
          return element;
        }, (error: unknown) => {
          this.images.delete(url);
          throw error;
        });
      image = { texture, ready };
      this.images.set(url, image);
    }
    const instance = image.texture.clone();
    image.ready.then(() => {
      instance.needsUpdate = true;
      onLoad?.(instance);
    }, onError);
    return instance;
  }
}

const manager = new LoadingManager();
const textures = new SharedTextureLoader(manager);
manager.addHandler(/\.(?:avif|webp|png)$/i, textures);

export const preferredModelLoader = new GLTFLoader(manager)
  .setMeshoptDecoder(MeshoptDecoder)
  .register((parser) => ({
    name: 'EXT_texture_webp',
    loadTexture(index) {
      const extensions = parser.json.textures[index].extensions;
      const preview = extensions?.EXT_texture_webp;
      if (!preview) return null;
      const load = (source: number) => {
        const uri = parser.json.images[source].uri;
        return parser.loadTextureImage(index, source, (uri && manager.getHandler(uri)) || parser.textureLoader);
      };
      const preferred = extensions.EXT_texture_avif;
      if (!preferred) return load(preview.source);
      return load(preferred.source).then((result) => result ?? load(preview.source));
    },
  }));
