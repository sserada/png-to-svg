import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Post } from '$lib/post';

// Mock crypto.randomUUID
vi.stubGlobal('crypto', {
  randomUUID: () => 'test-uuid-1234'
});

// Mock import.meta.env
vi.stubEnv('VITE_HOST', 'localhost');
vi.stubEnv('VITE_BACKEND_PORT', '8000');

describe('Post', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('should send file data and return success response', async () => {
    const mockResponse = {
      success: true,
      url: 'http://localhost:8000/backend/static/test.svg',
      filename: 'test.svg'
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockResponse)
    });

    const file = new File(['test'], 'test.png', { type: 'image/png' });
    const result = await Post(file, 'balanced');

    expect(result.success).toBe(true);
    expect(result.url).toBe(mockResponse.url);
    expect(result.filename).toBe('test.svg');
    expect(fetch).toHaveBeenCalledOnce();
  });

  it('should throw on HTTP error response', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      statusText: 'Bad Request',
      json: () => Promise.resolve({ detail: { error: 'Invalid file' } })
    });

    const file = new File(['test'], 'test.png', { type: 'image/png' });

    await expect(Post(file, 'balanced')).rejects.toMatchObject({
      message: 'Bad Request',
      detail: { error: 'Invalid file' }
    });
  });

  it('should throw network error when fetch fails', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('Network error'));

    const file = new File(['test'], 'test.png', { type: 'image/png' });

    await expect(Post(file, 'balanced')).rejects.toMatchObject({
      message: 'Network error'
    });
  });

  it('should use the specified preset', async () => {
    const mockResponse = { success: true, url: 'http://test/out.svg', filename: 'out.svg' };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockResponse)
    });

    const file = new File(['test'], 'test.png', { type: 'image/png' });
    await Post(file, 'high_quality');

    const callArgs = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    const body = JSON.parse(callArgs[1].body);
    expect(body.preset).toBe('high_quality');
  });

  it('should default to balanced preset', async () => {
    const mockResponse = { success: true, url: 'http://test/out.svg', filename: 'out.svg' };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockResponse)
    });

    const file = new File(['test'], 'test.png', { type: 'image/png' });
    await Post(file);

    const callArgs = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    const body = JSON.parse(callArgs[1].body);
    expect(body.preset).toBe('balanced');
  });

  it('should send file name and base64 data in request body', async () => {
    const mockResponse = { success: true, url: 'http://test/out.svg', filename: 'out.svg' };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockResponse)
    });

    const file = new File(['test content'], 'myimage.png', { type: 'image/png' });
    await Post(file, 'fast');

    const callArgs = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    const body = JSON.parse(callArgs[1].body);
    expect(body.name).toBe('myimage.png');
    expect(body.data).toContain('data:');
    expect(callArgs[1].headers['Content-Type']).toBe('application/json');
  });
});
