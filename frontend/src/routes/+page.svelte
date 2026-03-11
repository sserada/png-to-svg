<script lang='ts'>
  import JSZip from 'jszip';
  import pngIcon from '$lib/assets/png-icon.png';
  import { Post, ApiError, type ProgressEvent } from '$lib/post';
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

  import { onDestroy } from 'svelte';

  let files: FileList | undefined = $state(undefined);
  let fileStatuses: {[key: string]: FileStatus} = $state({});
  let selectedPreset: string = $state('balanced');
  let dragOver: boolean = $state(false);
  let previewUrls: string[] = $state([]);

  function revokePreviewUrls() {
    previewUrls.forEach(url => URL.revokeObjectURL(url));
    previewUrls = [];
  }

  function createPreviewUrl(file: File): string {
    const url = URL.createObjectURL(file);
    previewUrls.push(url);
    return url;
  }

  onDestroy(() => {
    revokePreviewUrls();
  });

  let isProcessing: boolean = $state(false);
  let completedCount = $derived(Object.values(fileStatuses).filter(s => s.status === 'completed').length);
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
      });

      if (data.success) {
        fileStatuses[key] = {
          status: 'completed',
          url: data.url,
          displayName: file.name,
          originalSize: data.original_size,
          svgSize: data.svg_size,
          conversionTimeMs: data.conversion_time_ms,
        };
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
      validEntries.push({ key, file });
    }

    await Promise.all(validEntries.map(({ key, file }) => processFile(key, file)));
    isProcessing = false;
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
      revokePreviewUrls();
      fileStatuses = {};
      downloadError = null;
      files = input.files;
    }
  }

  function handleDrop(e: DragEvent) {
    e.preventDefault();
    dragOver = false;
    if (e.dataTransfer?.files && e.dataTransfer.files.length > 0) {
      revokePreviewUrls();
      fileStatuses = {};
      downloadError = null;
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
    </select>
  </div>

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
        {#each Array.from(files) as file, i}
          {@const key = fileKey(i, file.name)}
          <tr>
            <td class="filename">{file.name}</td>
            <td>
              <img src={createPreviewUrl(file)} alt={file.name} class="preview-img" />
            </td>
            <td class="status-cell">
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

    .dropzone, .buttons, table {
      width: 100%;
    }

    .btn {
      width: 45%;
    }

    .divider {
      width: 10%;
    }
  }
</style>
