<script lang='ts'>
  import JSZip from 'jszip';
  import pngIcon from '$lib/assets/png-icon.png';
  import { Post } from '$lib/post';
  import type { PostResult } from '$lib/post';
  import { FileDropzone } from '@skeletonlabs/skeleton';
  import { saveAs } from 'file-saver';

  let files: FileList;
  let results: {[key: string]: string} = {};
  let isProcessing = false;
  let fileStatuses: {[key: string]: 'pending' | 'processing' | 'done' | 'error'} = {};
  let fileErrors: {[key: string]: string} = {};
  let errorMessage = '';
  let successMessage = '';
  let warningMessage = '';

  /** Filter files to only include PNGs and set a warning if non-PNGs were dropped */
  function validateAndFilterFiles(inputFiles: FileList): File[] {
    const allFiles = Array.from(inputFiles);
    const pngFiles = allFiles.filter((f) => f.type === 'image/png');
    const rejected = allFiles.length - pngFiles.length;

    if (rejected > 0) {
      warningMessage = `${rejected} non-PNG file(s) were removed. Only PNG files are accepted.`;
    } else {
      warningMessage = '';
    }

    return pngFiles;
  }

  /** Reactive statement: validate files whenever they change */
  $: validFiles = files ? validateAndFilterFiles(files) : [];

  async function send() {
    if (!validFiles.length) return;

    // Reset state
    isProcessing = true;
    errorMessage = '';
    successMessage = '';
    results = {};
    fileStatuses = {};
    fileErrors = {};

    // Initialize all file statuses to pending
    for (const file of validFiles) {
      fileStatuses[file.name] = 'pending';
    }

    let successCount = 0;
    let errorCount = 0;

    // Process all files concurrently and await all
    const promises = validFiles.map(async (file) => {
      fileStatuses[file.name] = 'processing';
      fileStatuses = fileStatuses; // trigger reactivity

      const result: PostResult = await Post(file);

      if (result.success) {
        results[file.name] = result.url;
        results = results; // trigger reactivity
        fileStatuses[file.name] = 'done';
        successCount++;
      } else {
        fileStatuses[file.name] = 'error';
        fileErrors[file.name] = result.error;
        fileErrors = fileErrors; // trigger reactivity
        errorCount++;
      }

      fileStatuses = fileStatuses; // trigger reactivity
    });

    await Promise.all(promises);

    // Show summary message
    if (errorCount === 0) {
      successMessage = `All ${successCount} file(s) converted successfully!`;
    } else if (successCount === 0) {
      errorMessage = `All ${errorCount} file(s) failed to convert. Please try again.`;
    } else {
      successMessage = `${successCount} file(s) converted successfully.`;
      errorMessage = `${errorCount} file(s) failed to convert.`;
    }

    isProcessing = false;
  }

  async function download() {
    const zip = new JSZip();
    for (const [filename, url] of Object.entries(results)) {
      const response = await fetch(url);
      const blob = await response.blob();
      zip.file(filename.replace('.png', '.svg'), blob);
    }
    const content = await zip.generateAsync({type: "blob"});
    saveAs(content, "SVGs.zip");
  }
</script>

<svelte:head>
  <title>PNG to SVG</title>
</svelte:head>

<section>
  <h1>PNG to SVG</h1>
  <FileDropzone name="files" bind:files multiple accept="image/png">
	  <svelte:fragment slot="lead">
      <img src={pngIcon} class="icon" alt="PNG icon" />
    </svelte:fragment>
	  <svelte:fragment slot="message">Upload a file or drag and drop</svelte:fragment>
	  <svelte:fragment slot="meta">Only PNG files are allowed</svelte:fragment>
  </FileDropzone>

  {#if warningMessage}
    <aside class="alert variant-ghost-warning">
      <p>{warningMessage}</p>
    </aside>
  {/if}

  {#if errorMessage}
    <aside class="alert variant-ghost-error">
      <p>{errorMessage}</p>
    </aside>
  {/if}

  {#if successMessage}
    <aside class="alert variant-ghost-success">
      <p>{successMessage}</p>
    </aside>
  {/if}

  <div class="buttons">
    <button
      type="button"
      class="btn variant-filled send"
      on:click={send}
      disabled={isProcessing || !validFiles.length}
    >
      {isProcessing ? 'Converting...' : 'Send'}
    </button>
    {#if Object.keys(results).length > 0}
      <div class="divider"></div>
      <button type="button" class="btn variant-filled download" on:click={download}>Download</button>
    {/if}
  </div>

  {#if validFiles.length > 0}
    <table>
      <thead>
        <tr>
          <th>PNG</th>
          <th>SVG</th>
        </tr>
      </thead>
      <tbody>
        {#each validFiles as file}
          <tr>
            <td>
              <img src={URL.createObjectURL(file)} alt={file.name} />
            </td>
            <td>
              {#if fileStatuses[file.name] === 'processing'}
                <p class="status-processing">Converting...</p>
              {:else if fileStatuses[file.name] === 'error'}
                <p class="status-error">Error: {fileErrors[file.name] ?? 'Unknown error'}</p>
              {:else if results[file.name]}
                <img src={results[file.name]} alt="{file.name} converted" />
              {:else}
                <p>Unprocessed</p>
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

  .buttons {
    display: flex;
    width: 50%;
    margin-top: 2rem;
  }

  button {
    width: 20%;
    margin: 0 auto;
  }

  button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .alert {
    margin-top: 1rem;
    padding: 0.75rem 1.25rem;
    border-radius: 0.5rem;
    width: 50%;
    text-align: center;
  }

  .variant-ghost-warning {
    background-color: rgba(234, 179, 8, 0.15);
    color: #ca8a04;
    border: 1px solid rgba(234, 179, 8, 0.3);
  }

  .variant-ghost-error {
    background-color: rgba(239, 68, 68, 0.15);
    color: #dc2626;
    border: 1px solid rgba(239, 68, 68, 0.3);
  }

  .variant-ghost-success {
    background-color: rgba(34, 197, 94, 0.15);
    color: #16a34a;
    border: 1px solid rgba(34, 197, 94, 0.3);
  }

  .status-processing {
    color: #2563eb;
    font-style: italic;
  }

  .status-error {
    color: #dc2626;
    font-size: 0.85rem;
  }

  table {
    width: 50%;
    border-collapse: collapse;
    margin-top: 2rem;
    margin-bottom: 2rem;
  }

  th, td {
    width: 50%;
    border: 1px dashed #ccc;
    padding: 8px 12px;
    text-align: center;
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

    .alert {
      width: 90%;
    }
  }
</style>
