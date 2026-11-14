import manifest from '../../../saydraft/models/manifest.json' with { type: 'json' };

type CatalogModel = { id: string; source: string; license: string; requires?: string[]; files: { size: number; bundled_source?: string }[] };
const catalog: readonly CatalogModel[] = manifest.models;
const models = new Map(catalog.map((model) => [model.id, model]));
export function modelDownload(id: string) {
  const seen = new Set<string>();
  function collect(key: string): CatalogModel[] {
    if (seen.has(key)) return [];
    const model = models.get(key);
    if (!model) throw new Error(`Missing documented model: ${key}`);
    seen.add(key);
    return [model, ...(model.requires ?? []).flatMap(collect)];
  }
  const bundle = collect(id);
  const bytes = bundle.flatMap((model) => model.files).reduce((sum, file) => sum + ('bundled_source' in file ? 0 : file.size), 0);
  return { id, bytes, mb: (bytes / 1_000_000).toFixed(bytes < 1_000_000 ? 2 : 1),
    license: [...new Set(bundle.map((model) => model.license))].join(' + '), source: bundle[0].source };
}
export const speechDownloads = [
  ['parakeet-tdt-0-6b-v3-int8', 'Default: Parakeet v3 + language detector'],
  ['parakeet-tdt-0-6b-v2-int8', 'English max: Parakeet v2'],
  ['whisper-base', 'Whisper base'], ['whisper-small', 'Whisper small'], ['whisper-medium', 'Whisper medium'],
  ['whisper-large-v3-turbo', 'All languages: Whisper turbo'],
  ['silero-vad-v5', 'Optional Silero speech detection'], ['gtcrn-speech-enhancement', 'Optional GTCRN quiet-speech enhancement'],
].map(([id, name]) => ({ name, ...modelDownload(id) }));

export const editingDownloads = [
  ['qwen35-08b-q4-k-m', 'Qwen3.5 0.8B cleanup'], ['qwen35-2b-q4-k-m', 'Qwen3.5 2B cleanup'],
  ['qwen35-4b-q4-k-m', 'Qwen3.5 4B experimental editing'],
  ['llama-cpp-b12110-cpu-x64', 'llama.cpp CPU runtime'], ['llama-cpp-b12110-vulkan-x64', 'llama.cpp Vulkan runtime'],
].map(([id, name]) => ({ name, ...modelDownload(id) }));
