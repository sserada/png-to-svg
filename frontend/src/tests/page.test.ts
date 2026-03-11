import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/svelte';
import Page from '../routes/+page.svelte';

// Mock modules before importing the component
vi.mock('$lib/post', () => ({
  Post: vi.fn(),
  ApiError: class ApiError extends Error {
    status: number;
    detail: Record<string, unknown>;
    constructor(message: string, status: number, detail: Record<string, unknown>) {
      super(message);
      this.name = 'ApiError';
      this.status = status;
      this.detail = detail;
    }
  },
}));

vi.mock('$lib/validate', () => ({
  validateFile: vi.fn(() => null),
}));

vi.mock('file-saver', () => ({
  saveAs: vi.fn(),
}));

vi.mock('jszip', () => {
  return {
    default: vi.fn(() => ({
      file: vi.fn(),
      generateAsync: vi.fn().mockResolvedValue(new Blob()),
    })),
  };
});

vi.mock('$lib/assets/png-icon.png', () => ({ default: 'mock-icon.png' }));

function createMockFileList(files: File[]): FileList {
  const fileList = Object.create(FileList.prototype);
  for (let i = 0; i < files.length; i++) {
    fileList[i] = files[i];
  }
  Object.defineProperty(fileList, 'length', { value: files.length });
  fileList.item = (index: number) => files[index] ?? null;
  fileList[Symbol.iterator] = function* () {
    for (let i = 0; i < files.length; i++) yield files[i];
  };
  return fileList as FileList;
}

async function selectFiles(files: File[]) {
  const input = document.getElementById('file-input') as HTMLInputElement;
  const fileList = createMockFileList(files);
  Object.defineProperty(input, 'files', { value: fileList, configurable: true });
  await fireEvent.change(input);
}

describe('+page.svelte', () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it('should render the page title and dropzone', () => {
    render(Page);
    expect(screen.getByText('Image to SVG')).toBeInTheDocument();
    expect(screen.getByText('Upload a file or drag and drop')).toBeInTheDocument();
  });

  it('should render the preset selector with all options', () => {
    render(Page);
    const select = screen.getByLabelText('Quality Preset:') as HTMLSelectElement;
    expect(select).toBeInTheDocument();
    const options = select.querySelectorAll('option');
    const values = Array.from(options).map(o => o.value);
    expect(values).toContain('high_quality');
    expect(values).toContain('balanced');
    expect(values).toContain('fast');
    expect(values).toContain('custom');
  });

  it('should have Send button disabled when no files selected', () => {
    render(Page);
    const sendBtn = screen.getByRole('button', { name: 'Send' });
    expect(sendBtn).toBeDisabled();
  });

  it('should populate file table when files are selected', async () => {
    render(Page);
    await selectFiles([
      new File(['content1'], 'image1.png', { type: 'image/png' }),
      new File(['content2'], 'image2.jpg', { type: 'image/jpeg' }),
    ]);

    expect(screen.getByText('image1.png')).toBeInTheDocument();
    expect(screen.getByText('image2.jpg')).toBeInTheDocument();
  });

  it('should enable Send button when files are selected', async () => {
    render(Page);
    await selectFiles([
      new File(['content'], 'test.png', { type: 'image/png' }),
    ]);

    const sendBtn = screen.getByRole('button', { name: 'Send' });
    expect(sendBtn).not.toBeDisabled();
  });

  it('should show validation error for invalid files on send', async () => {
    const { validateFile } = await import('$lib/validate');
    vi.mocked(validateFile).mockReturnValue('Supported formats: PNG, JPG/JPEG, WebP, BMP, GIF');

    render(Page);
    await selectFiles([
      new File(['content'], 'doc.pdf', { type: 'application/pdf' }),
    ]);
    await fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    expect(screen.getByText('Supported formats: PNG, JPG/JPEG, WebP, BMP, GIF')).toBeInTheDocument();
  });

  it('should show custom params panel when custom preset is selected', async () => {
    render(Page);
    const select = screen.getByLabelText('Quality Preset:') as HTMLSelectElement;
    await fireEvent.change(select, { target: { value: 'custom' } });

    expect(screen.getByLabelText(/Filter Speckle/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Color Precision/)).toBeInTheDocument();
    expect(document.getElementById('cp-mode')).toBeInTheDocument();
  });

  it('should clear files and statuses when Clear All is clicked', async () => {
    const { Post } = await import('$lib/post');
    vi.mocked(Post).mockResolvedValue({
      success: true,
      url: 'http://test/out.svg',
      filename: 'out.svg',
      original_size: 100,
      svg_size: 200,
      conversion_time_ms: 50,
    });

    render(Page);
    await selectFiles([
      new File(['content'], 'test.png', { type: 'image/png' }),
    ]);
    await fireEvent.click(screen.getByRole('button', { name: 'Send' }));

    await vi.waitFor(() => {
      expect(screen.getByText('Clear All')).toBeInTheDocument();
    });

    await fireEvent.click(screen.getByText('Clear All'));

    expect(screen.queryByText('test.png')).not.toBeInTheDocument();
  });

  it('should not show Download button before any conversion completes', () => {
    render(Page);
    expect(screen.queryByText(/Download/)).not.toBeInTheDocument();
  });
});
