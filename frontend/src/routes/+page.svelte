<script lang='ts'>
  import JSZip from 'jszip';
  import pngIcon from '$lib/assets/png-icon.png';
  import { Post, ApiError, type ProgressEvent, type CustomParams } from '$lib/post';
  import { validateFile } from '$lib/validate';
  import { saveAs } from 'file-saver';

  type ConversionStatus = 'pending' | 'processing' | 'completed' | 'failed';

  interface FileStatus {
    url?: string;
    status: ConversionStatus;
    error?: string;
    stage?: string;
    progress?: number;
    displayName: string;
    originalSize?: number;
    svgSize?: number;
    conversionTimeMs?: number;
  }

  function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  import { onDestroy, onMount } from 'svelte';

  interface HistoryEntry {
    filename: string;
    date: string;
    preset: string;
    originalSize?: number;
    svgSize?: number;
    conversionTimeMs?: number;
  }

  const HISTORY_KEY = 'svg-conversion-history';
  const MAX_HISTORY = 20;

  function loadHistory(): HistoryEntry[] {
    try {
      const stored = localStorage.getItem(HISTORY_KEY);
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  }

  function saveHistory(entries: HistoryEntry[]) {
    try {
      localStorage.setItem(HISTORY_KEY, JSON.stringify(entries.slice(0, MAX_HISTORY)));
    } catch {
      // QuotaExceededError - silently ignore
    }
  }

  function addToHistory(entry: HistoryEntry) {
    const entries = loadHistory();
    entries.unshift(entry);
    saveHistory(entries);
    history = entries.slice(0, MAX_HISTORY);
  }

  function clearHistory() {
    localStorage.removeItem(HISTORY_KEY);
    history = [];
  }

  let history: HistoryEntry[] = $state([]);
  let showHistory: boolean = $state(false);

  let files: FileList | undefined = $state(undefined);
  let fileStatuses: {[key: string]: FileStatus} = $state({});
  let selectedPreset: string = $state('balanced');
  let customParams: CustomParams = $state({
    colormode: 'color',
    mode: 'spline',
    filter_speckle: 4,
    color_precision: 6,
    layer_difference: 16,
    corner_threshold: 60,
    length_threshold: 4.0,
    max_iterations: 10,
    splice_threshold: 45,
    path_precision: 3,
  });
  let isCustom = $derived(selectedPreset === 'custom');
  let dragOver: boolean = $state(false);
  let previewUrlMap: Map<File, string> = $state(new Map());

  function revokePreviewUrls() {
    previewUrlMap.forEach(url => URL.revokeObjectURL(url));
    previewUrlMap = new Map();
  }

  function getPreviewUrl(file: File): string {
    const existing = previewUrlMap.get(file);
    if (existing) return existing;
    const url = URL.createObjectURL(file);
    previewUrlMap.set(file, url);
    return url;
  }

  onMount(() => {
    history = loadHistory();
  });

  onDestroy(() => {
    revokePreviewUrls();
  });

  let fileMap: {[key: string]: File} = $state({});
  let isProcessing: boolean = $state(false);
  let completedCount = $derived(Object.values(fileStatuses).filter(s => s.status === 'completed').length);
  let hasStatuses = $derived(Object.keys(fileStatuses).length > 0);
  let hasCompleted = $derived(completedCount > 0);
  let downloadError: string | null = $state(null);
  let isDownloading: boolean = $state(false);

  function fileKey(index: number, name: string): string {
    return `${index}:${name}`;
  }

  async function processFile(key: string, file: File) {
    fileStatuses[key] = { status: 'processing', stage: 'uploading', progress: 0, displayName: file.name };

    try {
      const data = await Post(file, selectedPreset, (evt: ProgressEvent) => {
        if (fileStatuses[key]?.status === 'processing') {
          fileStatuses[key] = {
            ...fileStatuses[key],
            stage: evt.stage,
            progress: evt.progress
          };
        }
      }, isCustom ? customParams : undefined);

      if (data.success) {
        fileStatuses[key] = {
          status: 'completed',
          url: data.url,
          displayName: file.name,
          originalSize: data.original_size,
          svgSize: data.svg_size,
          conversionTimeMs: data.conversion_time_ms,
        };
        addToHistory({
          filename: file.name,
          date: new Date().toISOString(),
          preset: selectedPreset,
          originalSize: data.original_size,
          svgSize: data.svg_size,
          conversionTimeMs: data.conversion_time_ms,
        });
      } else {
        fileStatuses[key] = {
          status: 'failed',
          error: 'Conversion failed',
          displayName: file.name
        };
      }
    } catch (error: unknown) {
      const message = error instanceof ApiError
        ? (error.detail as { error?: string })?.error || error.message
        : error instanceof Error ? error.message : 'An unexpected error occurred';
      fileStatuses[key] = {
        status: 'failed',
        error: message,
        displayName: file.name
      };
    }
  }

  async function send() {
    if (!files) return;
    isProcessing = true;
    const validEntries: { key: string; file: File }[] = [];

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const key = fileKey(i, file.name);

      fileMap[key] = file;
      const validationError = validateFile(file);
      if (validationError) {
        fileStatuses[key] = {
          status: 'failed',
          error: validationError,
          displayName: file.name
        };
        continue;
      }

      fileStatuses[key] = { status: 'pending', displayName: file.name };
      fileMap[key] = file;
      validEntries.push({ key, file });
    }

    const CONCURRENCY_LIMIT = 3;
    for (let i = 0; i < validEntries.length; i += CONCURRENCY_LIMIT) {
      const batch = validEntries.slice(i, i + CONCURRENCY_LIMIT);
      await Promise.all(batch.map(({ key, file }) => processFile(key, file)));
    }
    isProcessing = false;
  }

  async function retryFile(key: string) {
    const file = fileMap[key];
    if (!file || fileStatuses[key]?.status === 'processing') return;
    await processFile(key, file);
  }

  function resetFileState() {
    revokePreviewUrls();
    fileStatuses = {};
    fileMap = {};
    downloadError = null;
  }

  function clearAll() {
    resetFileState();
    files = undefined;
  }

  async function download() {
    downloadError = null;
    isDownloading = true;
    try {
      const zip = new JSZip();
      for (const [, status] of Object.entries(fileStatuses)) {
        if (status.status === 'completed' && status.url) {
          const response = await fetch(status.url);
          if (!response.ok) {
            throw new Error(`Failed to fetch ${status.displayName}`);
          }
          const blob = await response.blob();
          const svgFilename = status.displayName.replace(/\.(png|jpg|jpeg|webp|bmp|gif)$/i, '.svg');
          zip.file(svgFilename, blob);
        }
      }
      const content = await zip.generateAsync({type: "blob"});
      saveAs(content, "SVGs.zip");
    } catch (error: unknown) {
      downloadError = error instanceof Error ? error.message : 'Download failed';
    } finally {
      isDownloading = false;
    }
  }

  function handleFileInput(e: Event) {
    const input = e.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      resetFileState();
      files = input.files;
    }
  }

  const SUPPORTED_EXTENSIONS = /\.(png|jpg|jpeg|webp|bmp|gif)$/i;

  async function readEntryAsFile(entry: FileSystemFileEntry): Promise<File> {
    return new Promise((resolve, reject) => {
      entry.file(resolve, reject);
    });
  }

  async function readDirectoryEntries(dirEntry: FileSystemDirectoryEntry): Promise<File[]> {
    const reader = dirEntry.createReader();
    const files: File[] = [];

    const readBatch = (): Promise<FileSystemEntry[]> =>
      new Promise((resolve, reject) => reader.readEntries(resolve, reject));

    let batch: FileSystemEntry[];
    do {
      batch = await readBatch();
      for (const entry of batch) {
        if (entry.isFile && SUPPORTED_EXTENSIONS.test(entry.name)) {
          files.push(await readEntryAsFile(entry as FileSystemFileEntry));
        } else if (entry.isDirectory) {
          files.push(...await readDirectoryEntries(entry as FileSystemDirectoryEntry));
        }
      }
    } while (batch.length > 0);

    return files;
  }

  function filesToFileList(fileArray: File[]): FileList {
    const dt = new DataTransfer();
    for (const file of fileArray) {
      dt.items.add(file);
    }
    return dt.files;
  }

  async function handleDrop(e: DragEvent) {
    e.preventDefault();
    dragOver = false;

    if (!e.dataTransfer?.items || e.dataTransfer.items.length === 0) return;

    const items = Array.from(e.dataTransfer.items);
    const hasEntries = items.some(item => item.webkitGetAsEntry?.()?.isDirectory);

    if (hasEntries) {
      const extractedFiles: File[] = [];
      for (const item of items) {
        const entry = item.webkitGetAsEntry();
        if (!entry) continue;
        try {
          if (entry.isFile && SUPPORTED_EXTENSIONS.test(entry.name)) {
            extractedFiles.push(await readEntryAsFile(entry as FileSystemFileEntry));
          } else if (entry.isDirectory) {
            extractedFiles.push(...await readDirectoryEntries(entry as FileSystemDirectoryEntry));
          }
        } catch {
          // Skip unreadable entries
        }
      }
      if (extractedFiles.length > 0) {
        resetFileState();
        files = filesToFileList(extractedFiles);
      }
    } else if (e.dataTransfer.files.length > 0) {
      resetFileState();
      files = e.dataTransfer.files;
    }
  }

  function handleDragOver(e: DragEvent) {
    e.preventDefault();
    dragOver = true;
  }

  function handleDragLeave() {
    dragOver = false;
  }
</script>

<svelte:head>
  <title>Image to SVG</title>
</svelte:head>

<section>
  <h1>Image to SVG</h1>

  <div
    class="dropzone"
    class:drag-over={dragOver}
    role="button"
    tabindex="0"
    aria-label="Upload image files for SVG conversion"
    ondrop={handleDrop}
    ondragover={handleDragOver}
    ondragleave={handleDragLeave}
    onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); document.getElementById('file-input')?.click(); } }}
    onclick={() => document.getElementById('file-input')?.click()}
  >
    <img src={pngIcon} class="icon" alt="Upload icon" />
    <p class="dropzone-message">Upload a file or drag and drop</p>
    <p class="dropzone-meta">PNG, JPG/JPEG, WebP, BMP, GIF files are supported</p>
    <input
      id="file-input"
      type="file"
      multiple
      accept=".png,.jpg,.jpeg,.webp,.bmp,.gif"
      onchange={handleFileInput}
      hidden
    />
  </div>

  <div class="preset-selector">
    <label for="preset">Quality Preset:</label>
    <select id="preset" bind:value={selectedPreset} class="select" title="Select conversion quality preset">
      <option value="high_quality" title="Best detail, larger SVG, slower conversion">High Quality</option>
      <option value="balanced" title="Good balance of detail, size, and speed">Balanced</option>
      <option value="fast" title="Fastest conversion, smaller SVG, less detail">Fast</option>
      <option value="custom" title="Fine-tune conversion parameters">Custom</option>
    </select>
  </div>

  {#if isCustom}
    <div class="custom-params">
      <div class="param-row">
        <label for="cp-filter-speckle">Filter Speckle <span class="param-value">{customParams.filter_speckle}</span></label>
        <input id="cp-filter-speckle" type="range" min="1" max="128" bind:value={customParams.filter_speckle} />
      </div>
      <div class="param-row">
        <label for="cp-color-precision">Color Precision <span class="param-value">{customParams.color_precision}</span></label>
        <input id="cp-color-precision" type="range" min="1" max="8" bind:value={customParams.color_precision} />
      </div>
      <div class="param-row">
        <label for="cp-layer-difference">Layer Difference <span class="param-value">{customParams.layer_difference}</span></label>
        <input id="cp-layer-difference" type="range" min="1" max="256" bind:value={customParams.layer_difference} />
      </div>
      <div class="param-row">
        <label for="cp-corner-threshold">Corner Threshold <span class="param-value">{customParams.corner_threshold}</span></label>
        <input id="cp-corner-threshold" type="range" min="0" max="180" bind:value={customParams.corner_threshold} />
      </div>
      <div class="param-row">
        <label for="cp-length-threshold">Length Threshold <span class="param-value">{customParams.length_threshold}</span></label>
        <input id="cp-length-threshold" type="range" min="0" max="20" step="0.5" bind:value={customParams.length_threshold} />
      </div>
      <div class="param-row">
        <label for="cp-max-iterations">Max Iterations <span class="param-value">{customParams.max_iterations}</span></label>
        <input id="cp-max-iterations" type="range" min="1" max="50" bind:value={customParams.max_iterations} />
      </div>
      <div class="param-row">
        <label for="cp-splice-threshold">Splice Threshold <span class="param-value">{customParams.splice_threshold}</span></label>
        <input id="cp-splice-threshold" type="range" min="0" max="180" bind:value={customParams.splice_threshold} />
      </div>
      <div class="param-row">
        <label for="cp-path-precision">Path Precision <span class="param-value">{customParams.path_precision}</span></label>
        <input id="cp-path-precision" type="range" min="1" max="10" bind:value={customParams.path_precision} />
      </div>
      <div class="param-row">
        <label for="cp-mode">Mode</label>
        <select id="cp-mode" bind:value={customParams.mode} class="select-small">
          <option value="spline">Spline</option>
          <option value="polygon">Polygon</option>
          <option value="none">None</option>
        </select>
      </div>
      <div class="param-row">
        <label for="cp-colormode">Color Mode</label>
        <select id="cp-colormode" bind:value={customParams.colormode} class="select-small">
          <option value="color">Color</option>
          <option value="binary">Binary</option>
        </select>
      </div>
    </div>
  {/if}

  <div class="buttons">
    <button type="button" class="btn send" onclick={send} disabled={!files || files.length === 0 || isProcessing}>
      {#if isProcessing}
        Processing...
      {:else}
        Send
      {/if}
    </button>
    {#if hasCompleted}
      <div class="divider"></div>
      <button type="button" class="btn download" onclick={download} disabled={isDownloading}>
        {#if isDownloading}
          Downloading...
        {:else}
          Download ({completedCount})
        {/if}
      </button>
    {/if}
  </div>

  {#if hasStatuses && !isProcessing}
    <button type="button" class="btn-clear" onclick={clearAll}>Clear All</button>
  {/if}

  {#if downloadError}
    <div class="download-error">
      <span>{downloadError}</span>
      <button type="button" class="dismiss-btn" onclick={() => downloadError = null} aria-label="Dismiss error">&times;</button>
    </div>
  {/if}

  {#if files && files.length > 0}
    <table>
      <thead>
        <tr>
          <th>Filename</th>
          <th>Preview</th>
          <th>Status</th>
          <th>SVG Preview</th>
        </tr>
      </thead>
      <tbody>
        {#each Array.from(files) as file, i (fileKey(i, file.name))}
          {@const key = fileKey(i, file.name)}
          <tr>
            <td class="filename">{file.name}</td>
            <td>
              <img src={getPreviewUrl(file)} alt={file.name} class="preview-img" />
            </td>
            <td class="status-cell" aria-live="polite">
              {#if fileStatuses[key]}
                {#if fileStatuses[key].status === 'pending'}
                  <span class="badge badge-pending">Pending</span>
                {:else if fileStatuses[key].status === 'processing'}
                  <div class="processing">
                    <div class="spinner"></div>
                    <span class="stage-label">
                      {#if fileStatuses[key].stage === 'uploading'}
                        Uploading...
                      {:else if fileStatuses[key].stage === 'decoding'}
                        Decoding...
                      {:else if fileStatuses[key].stage === 'saving'}
                        Saving...
                      {:else if fileStatuses[key].stage === 'converting'}
                        Converting...
                      {:else}
                        Processing...
                      {/if}
                    </span>
                    {#if fileStatuses[key].progress != null}
                      <div class="progress-bar">
                        <div class="progress-fill" style="width: {fileStatuses[key].progress}%"></div>
                      </div>
                    {/if}
                  </div>
                {:else if fileStatuses[key].status === 'completed'}
                  <span class="badge badge-success">&#x2713; Completed</span>
                {:else if fileStatuses[key].status === 'failed'}
                  <div class="error-status">
                    <span class="badge badge-error">&#x2717; Failed</span>
                    <p class="error-message">{fileStatuses[key].error}</p>
                    <button type="button" class="btn-retry" onclick={() => retryFile(key)}>Retry</button>
                  </div>
                {/if}
              {:else}
                <span class="badge badge-default">Not started</span>
              {/if}
            </td>
            <td>
              {#if fileStatuses[key]?.status === 'completed' && fileStatuses[key].url}
                <img src={fileStatuses[key].url} alt="SVG output" class="preview-img" />
                {#if fileStatuses[key].originalSize != null}
                  <p class="metrics">
                    {formatSize(fileStatuses[key].originalSize ?? 0)} → {formatSize(fileStatuses[key].svgSize ?? 0)}
                    <br />{fileStatuses[key].conversionTimeMs}ms
                  </p>
                {/if}
                <a href={fileStatuses[key].url} download={fileStatuses[key].displayName.replace(/\.(png|jpg|jpeg|webp|bmp|gif)$/i, '.svg')} class="file-download-link">Download SVG</a>
              {:else if fileStatuses[key]?.status === 'processing'}
                <p class="text-muted">Converting...</p>
              {:else if fileStatuses[key]?.status === 'failed'}
                <p class="text-muted">-</p>
              {:else}
                <p class="text-muted">Waiting...</p>
              {/if}
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}

  {#if history.length > 0}
    <div class="history-section">
      <button type="button" class="btn-history-toggle" onclick={() => showHistory = !showHistory}>
        {showHistory ? 'Hide' : 'Show'} History ({history.length})
      </button>
      {#if showHistory}
        <div class="history-list">
          {#each history as entry}
            <div class="history-item">
              <span class="history-name">{entry.filename}</span>
              <span class="history-meta">
                {new Date(entry.date).toLocaleDateString()} &middot; {entry.preset}
                {#if entry.originalSize != null}
                  &middot; {formatSize(entry.originalSize)} → {formatSize(entry.svgSize ?? 0)}
                {/if}
                {#if entry.conversionTimeMs != null}
                  &middot; {entry.conversionTimeMs}ms
                {/if}
              </span>
            </div>
          {/each}
        </div>
        <button type="button" class="btn-clear-history" onclick={clearHistory}>Clear History</button>
      {/if}
    </div>
  {/if}

  <div class="footer">
    <p>&copy; 2024 <a href="https://hirawatasou.com" target="_blank">So Hirawata</a></p>
  </div>

</section>

<style>
  section {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    width: 80vw;
    max-width: 900px;
    margin: 0 auto;
    margin-top: 20vh;
  }

  h1 {
    font-size: 2rem;
    margin-bottom: 3rem;
  }

  .icon {
    width: 30%;
    max-width: 10rem;
    margin: 0 auto;
  }

  .dropzone {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    width: 50%;
    padding: 2rem;
    border: 2px dashed #94a3b8;
    border-radius: 12px;
    cursor: pointer;
    transition: border-color 0.2s, background-color 0.2s;
  }

  .dropzone:hover, .dropzone.drag-over {
    border-color: #3b82f6;
    background-color: rgba(59, 130, 246, 0.05);
  }

  .dropzone:focus-visible {
    outline: 2px solid #3b82f6;
    outline-offset: 2px;
  }

  .dropzone-message {
    margin-top: 1rem;
    font-size: 1rem;
    font-weight: 500;
  }

  .dropzone-meta {
    margin-top: 0.25rem;
    font-size: 0.85rem;
    color: #9ca3af;
  }

  .preset-selector {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-top: 1.5rem;
  }

  .preset-selector label {
    font-size: 0.9rem;
    font-weight: 500;
  }

  .preset-selector select {
    padding: 0.4rem 0.75rem;
    border-radius: 6px;
    border: 1px solid #ccc;
    font-size: 0.9rem;
    background: #f3f4f6;
  }

  .custom-params {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.5rem 1.5rem;
    width: 50%;
    margin-top: 1rem;
    padding: 1rem;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    background: #f9fafb;
  }

  .param-row {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
  }

  .param-row label {
    font-size: 0.8rem;
    font-weight: 500;
    color: #374151;
  }

  .param-value {
    font-weight: 600;
    color: #3b82f6;
  }

  .param-row input[type="range"] {
    width: 100%;
  }

  .select-small {
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
    border: 1px solid #ccc;
    font-size: 0.8rem;
    background: white;
  }

  .buttons {
    display: flex;
    width: 50%;
    margin-top: 1rem;
  }

  .btn {
    padding: 0.5rem 1.5rem;
    border-radius: 8px;
    border: none;
    font-size: 0.9rem;
    font-weight: 500;
    cursor: pointer;
    margin: 0 auto;
    transition: opacity 0.2s;
  }

  .btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn.send {
    background: #3b82f6;
    color: white;
  }

  .btn.send:hover:not(:disabled) {
    background: #2563eb;
  }

  .btn.download {
    background: #10b981;
    color: white;
  }

  .btn.download:hover {
    background: #059669;
  }

  table {
    width: 50%;
    border-collapse: collapse;
    margin-top: 2rem;
    margin-bottom: 2rem;
  }

  th, td {
    border: 1px dashed #ccc;
    padding: 8px 12px;
    text-align: center;
    vertical-align: middle;
  }

  th:nth-child(1), td.filename {
    width: 20%;
    text-align: left;
    font-size: 0.9rem;
    word-break: break-word;
  }

  th:nth-child(2), th:nth-child(4) {
    width: 25%;
  }

  th:nth-child(3), td.status-cell {
    width: 30%;
  }

  .preview-img {
    max-width: 100px;
    max-height: 100px;
    object-fit: contain;
  }

  .status-cell {
    min-height: 60px;
  }

  .processing {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.5rem;
  }

  .spinner {
    width: 24px;
    height: 24px;
    border: 3px solid #e5e7eb;
    border-top-color: #3b82f6;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .stage-label {
    font-size: 0.85rem;
    color: #6b7280;
  }

  .progress-bar {
    width: 80%;
    height: 6px;
    background: #e5e7eb;
    border-radius: 3px;
    overflow: hidden;
  }

  .progress-fill {
    height: 100%;
    background: #3b82f6;
    border-radius: 3px;
    transition: width 0.3s ease;
  }

  .error-status {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .error-message {
    font-size: 0.85rem;
    color: #dc2626;
    margin: 0;
    padding: 0.5rem;
    background-color: #fee2e2;
    border-radius: 4px;
  }

  .text-muted {
    color: #9ca3af;
    font-style: italic;
  }

  .metrics {
    margin-top: 0.25rem;
    font-size: 0.75rem;
    color: #6b7280;
    line-height: 1.4;
  }

  .badge {
    display: inline-block;
    padding: 0.25rem 0.75rem;
    border-radius: 9999px;
    font-size: 0.875rem;
    font-weight: 500;
  }

  .badge-pending {
    background: #e5e7eb;
    color: #6b7280;
  }

  .badge-success {
    background: #d1fae5;
    color: #065f46;
  }

  .badge-error {
    background: #fee2e2;
    color: #991b1b;
  }

  .badge-default {
    background: #f3f4f6;
    color: #9ca3af;
  }

  .download-error {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-top: 0.5rem;
    font-size: 0.85rem;
    color: #dc2626;
    padding: 0.5rem 1rem;
    background-color: #fee2e2;
    border-radius: 6px;
  }

  .dismiss-btn {
    background: none;
    border: none;
    color: #dc2626;
    font-size: 1.2rem;
    cursor: pointer;
    padding: 0 0.25rem;
    line-height: 1;
  }

  .dismiss-btn:hover {
    color: #991b1b;
  }

  .btn-retry {
    padding: 0.2rem 0.6rem;
    font-size: 0.75rem;
    border: 1px solid #3b82f6;
    border-radius: 4px;
    background: white;
    color: #3b82f6;
    cursor: pointer;
  }

  .btn-retry:hover {
    background: #eff6ff;
  }

  .btn-clear {
    margin-top: 0.5rem;
    padding: 0.3rem 0.8rem;
    font-size: 0.8rem;
    border: 1px solid #9ca3af;
    border-radius: 6px;
    background: white;
    color: #6b7280;
    cursor: pointer;
  }

  .btn-clear:hover {
    background: #f3f4f6;
    color: #374151;
  }

  .file-download-link {
    display: inline-block;
    margin-top: 0.25rem;
    font-size: 0.8rem;
    color: #3b82f6;
    text-decoration: none;
  }

  .file-download-link:hover {
    text-decoration: underline;
  }

  .history-section {
    width: 50%;
    margin-top: 1.5rem;
    margin-bottom: 3rem;
  }

  .btn-history-toggle {
    background: none;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    padding: 0.3rem 0.8rem;
    font-size: 0.8rem;
    color: #6b7280;
    cursor: pointer;
  }

  .btn-history-toggle:hover {
    background: #f3f4f6;
  }

  .history-list {
    margin-top: 0.5rem;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    overflow: hidden;
  }

  .history-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.5rem 0.75rem;
    border-bottom: 1px solid #f3f4f6;
    font-size: 0.8rem;
  }

  .history-item:last-child {
    border-bottom: none;
  }

  .history-name {
    font-weight: 500;
    color: #374151;
    word-break: break-word;
  }

  .history-meta {
    color: #9ca3af;
    font-size: 0.75rem;
    text-align: right;
    flex-shrink: 0;
    margin-left: 0.5rem;
  }

  .btn-clear-history {
    margin-top: 0.5rem;
    background: none;
    border: none;
    font-size: 0.75rem;
    color: #dc2626;
    cursor: pointer;
    padding: 0.2rem 0;
  }

  .btn-clear-history:hover {
    text-decoration: underline;
  }

  .footer {
    position: fixed;
    bottom: 3px;
  }

  .footer p {
    font-size: 0.9rem;
    opacity: 0.5;
  }

  @media (max-width: 768px) {
    section {
      width: 90vw;
    }

    .dropzone, .buttons, table, .custom-params, .history-section {
      width: 100%;
    }

    .custom-params {
      grid-template-columns: 1fr;
    }

    .btn {
      width: 45%;
    }

    .divider {
      width: 10%;
    }
  }
</style>
