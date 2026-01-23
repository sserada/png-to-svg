<script lang='ts'>
  import JSZip from 'jszip';
  import pngIcon from '$lib/assets/png-icon.png';
  import { Post } from '$lib/post';
  import { FileDropzone, ProgressRadial } from '@skeletonlabs/skeleton';
  import { saveAs } from 'file-saver';

  type ConversionStatus = 'pending' | 'processing' | 'completed' | 'failed';

  interface FileStatus {
    url?: string;
    status: ConversionStatus;
    error?: string;
  }

  let files: FileList;
  let fileStatuses: {[key: string]: FileStatus} = {};

  const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

  function validateFile(file: File): string | null {
    // Check file extension
    const validExtensions = ['.png', '.PNG'];
    const hasValidExtension = validExtensions.some(ext => file.name.endsWith(ext));

    if (!hasValidExtension) {
      return 'Only PNG files are allowed';
    }

    // Check file size
    if (file.size > MAX_FILE_SIZE) {
      return `File size exceeds ${MAX_FILE_SIZE / (1024 * 1024)}MB limit`;
    }

    return null;
  }

  async function send() {
    // Initialize all files as pending
    for (let i = 0; i < files.length; i++) {
      const file = files[i];

      // Validate file
      const validationError = validateFile(file);
      if (validationError) {
        fileStatuses[file.name] = {
          status: 'failed',
          error: validationError
        };
        continue;
      }

      fileStatuses[file.name] = { status: 'pending' };
    }

    // Process each file
    for (let i = 0; i < files.length; i++) {
      const file = files[i];

      // Skip if validation failed
      if (fileStatuses[file.name].status === 'failed') {
        continue;
      }

      // Update status to processing
      fileStatuses[file.name] = { status: 'processing' };

      try {
        const data = await Post(file);

        if (data.success) {
          fileStatuses[file.name] = {
            status: 'completed',
            url: data.url
          };
        } else {
          fileStatuses[file.name] = {
            status: 'failed',
            error: data.error || 'Conversion failed'
          };
        }
      } catch (error: any) {
        fileStatuses[file.name] = {
          status: 'failed',
          error: error.detail?.error || error.message || 'An unexpected error occurred'
        };
      }
    }
  }

  async function download() {
    const zip = new JSZip();
    for (const [filename, status] of Object.entries(fileStatuses)) {
      if (status.status === 'completed' && status.url) {
        const response = await fetch(status.url);
        const blob = await response.blob();
        zip.file(filename.replace('.png', '.svg').replace('.PNG', '.svg'), blob);
      }
    }
    const content = await zip.generateAsync({type: "blob"});
    saveAs(content, "SVGs.zip");
  }

  $: completedCount = Object.values(fileStatuses).filter(s => s.status === 'completed').length;
  $: hasCompleted = completedCount > 0;
</script>

<svelte:head>
  <title>PNG to SVG</title>
</svelte:head>

<section>
  <h1>PNG to SVG</h1>
  <FileDropzone name="files" bind:files multiple>
	  <svelte:fragment slot="lead">
      <img src={pngIcon} class="icon" alt="PNG icon" />
    </svelte:fragment>
	  <svelte:fragment slot="message">Upload a file or drag and drop</svelte:fragment>
	  <svelte:fragment slot="meta">Only PNG files are allowed</svelte:fragment>
  </FileDropzone>

  <div class="buttons">
    <button type="button" class="btn variant-filled send" on:click={send} disabled={!files || files.length === 0}>
      Send
    </button>
    {#if hasCompleted}
      <div class="divider"></div>
      <button type="button" class="btn variant-filled download" on:click={download}>
        Download ({completedCount})
      </button>
    {/if}
  </div>

  {#if files && files.length > 0}
    <table>
      <thead>
        <tr>
          <th>Filename</th>
          <th>PNG Preview</th>
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
                  <span class="badge variant-soft-secondary">Pending</span>
                {:else if fileStatuses[file.name].status === 'processing'}
                  <div class="processing">
                    <ProgressRadial width="w-8" stroke={100} meter="stroke-primary-500" />
                    <span>Processing...</span>
                  </div>
                {:else if fileStatuses[file.name].status === 'completed'}
                  <span class="badge variant-filled-success">✓ Completed</span>
                {:else if fileStatuses[file.name].status === 'failed'}
                  <div class="error-status">
                    <span class="badge variant-filled-error">✗ Failed</span>
                    <p class="error-message">{fileStatuses[file.name].error}</p>
                  </div>
                {/if}
              {:else}
                <span class="badge variant-soft">Not started</span>
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
    <p>©︎ 2023 <a href="https://hirawatasou.com" target="_blank">So Hirawata</a></p>
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

  .buttons {
    display: flex;
    width: 50%;
    margin-top: 2rem;
  }

  button {
    width: 20%;
    margin: 0 auto;
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

    buttons {
      width: 100%;
    }

    button {
      width: 45%;
    }

    .divider {
      width: 10%;
    }

    table {
      width: 100%;
    }
  }
</style>
