<script lang='ts'>
  import pngIcon from '$lib/assets/png-icon.png';
  import { Post } from '$lib/post';
  import { FileDropzone } from '@skeletonlabs/skeleton';

  let files: Filelist;
  let results: {[key: string]: string} = {};

  function send() {
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const res = Post(file);
      res.then((data) => {
        results[file.name] = data;
      });
    }
  }
</script>

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
                <a href={results[file.name]} download={file.name}>
                  <img src={results[file.name]} />
                </a>
              {:else}
                <p>Unprocessed</p>
              {/if}
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
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
    width: 10%;
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
