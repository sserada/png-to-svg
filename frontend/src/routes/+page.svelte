<script lang='ts'>
  import JSZip from 'jszip';
  import pngIcon from '$lib/assets/png-icon.png';
  import { Post } from '$lib/post';
  import { saveAs } from 'file-saver';

  type ConversionStatus = 'pending' | 'processing' | 'completed' | 'failed';

  interface FileStatus {
    url?: string;
    status: ConversionStatus;
    error?: string;
  }

  let files: FileList | undefined = $state(undefined);
  let fileStatuses: {[key: string]: FileStatus} = $state({});
  let selectedPreset: string = $state('balanced');
  let dragOver: boolean = $state(false);

  const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

  let completedCount = $derived(Object.values(fileStatuses).filter(s => s.status === 'completed').length);
  let hasCompleted = $derived(completedCount > 0);

  function validateFile(file: File): string | null {
    const validExtensions = ['.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif'];
    const lowerName = file.name.toLowerCase();
    const hasValidExtension = validExtensions.some(ext => lowerName.endsWith(ext));

    if (!hasValidExtension) {
      return 'Supported formats: PNG, JPG/JPEG, WebP, BMP, GIF';
    }

    if (file.size > MAX_FILE_SIZE) {
      return `File size exceeds ${MAX_FILE_SIZE / (1024 * 1024)}MB limit`;
    }

    return null;
  }

  async function processFile(file: File) {
    fileStatuses[file.name] = { status: 'processing' };

    try {
      const data = await Post(file, selectedPreset);

      if (data.success) {
        fileStatuses[file.name] = {
          status: 'completed',
          url: data.url
        };
      } else {
        fileStatuses[file.name] = {
          status: 'failed',
          error: 'Conversion failed'
        };
      }
    } catch (error: any) {
      fileStatuses[file.name] = {
        status: 'failed',
        error: error.detail?.error || error.message || 'An unexpected error occurred'
      };
    }
  }

  async function send() {
    if (!files) return;
    const validFiles: File[] = [];

    for (let i = 0; i < files.length; i++) {
      const file = files[i];

      const validationError = validateFile(file);
      if (validationError) {
        fileStatuses[file.name] = {
          status: 'failed',
          error: validationError
        };
        continue;
      }

      fileStatuses[file.name] = { status: 'pending' };
      validFiles.push(file);
    }

    await Promise.all(validFiles.map(file => processFile(file)));
  }

  async function download() {
    const zip = new JSZip();
    for (const [filename, status] of Object.entries(fileStatuses)) {
      if (status.status === 'completed' && status.url) {
        const response = await fetch(status.url);
        const blob = await response.blob();
        const svgFilename = filename.replace(/\.(png|jpg|jpeg|webp|bmp|gif)$/i, '.svg');
        zip.file(svgFilename, blob);
      }
    }
    const content = await zip.generateAsync({type: "blob"});
    saveAs(content, "SVGs.zip");
  }

  function handleFileInput(e: Event) {
    const input = e.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      files = input.files;
    }
  }

  function handleDrop(e: DragEvent) {
    e.preventDefault();
    dragOver = false;
    if (e.dataTransfer?.files && e.dataTransfer.files.length > 0) {
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
    ondrop={handleDrop}
    ondragover={handleDragOver}
    ondragleave={handleDragLeave}
    onkeydown={(e) => { if (e.key === 'Enter') document.getElementById('file-input')?.click(); }}
    onclick={() => document.getElementById('file-input')?.click()}
  >
    <img src={pngIcon} class="icon" alt="Image icon" />
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
    <select id="preset" bind:value={selectedPreset} class="select">
      <option value="high_quality">High Quality</option>
      <option value="balanced">Balanced</option>
      <option value="fast">Fast</option>
    </select>
  </div>

  <div class="buttons">
    <button type="button" class="btn send" onclick={send} disabled={!files || files.length === 0}>
      Send
    </button>
    {#if hasCompleted}
      <div class="divider"></div>
      <button type="button" class="btn download" onclick={download}>
        Download ({completedCount})
      </button>
    {/if}
  </div>

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
        {#each Array.from(files) as file}
          <tr>
            <td class="filename">{file.name}</td>
            <td>
              <img src={URL.createObjectURL(file)} alt={file.name} class="preview-img" />
            </td>
            <td class="status-cell">
              {#if fileStatuses[file.name]}
                {#if fileStatuses[file.name].status === 'pending'}
                  <span class="badge badge-pending">Pending</span>
                {:else if fileStatuses[file.name].status === 'processing'}
                  <div class="processing">
                    <div class="spinner"></div>
                    <span>Processing...</span>
                  </div>
                {:else if fileStatuses[file.name].status === 'completed'}
                  <span class="badge badge-success">&#x2713; Completed</span>
                {:else if fileStatuses[file.name].status === 'failed'}
                  <div class="error-status">
                    <span class="badge badge-error">&#x2717; Failed</span>
                    <p class="error-message">{fileStatuses[file.name].error}</p>
                  </div>
                {/if}
              {:else}
                <span class="badge badge-default">Not started</span>
              {/if}
            </td>
            <td>
              {#if fileStatuses[file.name]?.status === 'completed' && fileStatuses[file.name].url}
                <img src={fileStatuses[file.name].url} alt="SVG output" class="preview-img" />
              {:else if fileStatuses[file.name]?.status === 'processing'}
                <p class="text-muted">Converting...</p>
              {:else if fileStatuses[file.name]?.status === 'failed'}
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
    <p>&copy; 2023 <a href="https://hirawatasou.com" target="_blank">So Hirawata</a></p>
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
