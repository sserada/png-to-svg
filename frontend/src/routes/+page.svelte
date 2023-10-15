<script lang='ts'>
  import JSZip from 'jszip';
  import pngIcon from '$lib/assets/png-icon.png';
  import { Post } from '$lib/post';
  import { FileDropzone } from '@skeletonlabs/skeleton';
  import { saveAs } from 'file-saver';

  let files: Filelist;
  let results: {[key: string]: string} = {};
  let tableData: TableSource;

  function send() {
    for (let i = 0; i < files.length; i++) {
      const res = Post(files[i]);
      res.then((data) => {
        results[files[i].name] = data.url;
      });
    }
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
  <FileDropzone name="files" bind:files multiple>
	  <svelte:fragment slot="lead">
      <img src={pngIcon} class="icon" alt="PNG icon" />
    </svelte:fragment>
	  <svelte:fragment slot="message">Upload a file or drag and drop</svelte:fragment>
	  <svelte:fragment slot="meta">Only PNG files are allowed</svelte:fragment>
  </FileDropzone>

  <button type="button" class="btn variant-filled" on:click={send}>Send</button>

  {#if files}
    <table>
      <thead>
        <tr>
          <th>PNG</th>
          <th>SVG</th>
        </tr>
      </thead>
      <tbody>
        {#each files as file}
          <tr>
            <td>
              <img src={URL.createObjectURL(file)} />
            </td>
            <td>
              {#if results[file.name]}
                <img src={results[file.name]} />
              {:else}
                <p>Unprocessed</p>
              {/if}
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}

  {#if Object.keys(results).length > 0}
    <button type="button" class="btn variant-filled download" on:click={download}>Download</button>
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

  button {
    width: 12%;
    margin-top: 2rem;
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

  .download {
    margin-bottom: 2rem;
  }

  .footer {
    position: absolute;
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

    button {
      width: 30%;
    }

    table {
      width: 100%;
    }
  }
</style>
