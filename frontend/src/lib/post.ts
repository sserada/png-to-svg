/**
 * API client for image-to-SVG conversion.
 *
 * Handles file upload via base64-encoded POST, SSE progress streaming,
 * and request timeout management.
 */

interface ApiResponse {
  success: boolean;
  url: string;
  filename: string;
  original_size?: number;
  svg_size?: number;
  conversion_time_ms?: number;
}

export class ApiError extends Error {
  status: number;
  detail: { error: string; code?: string } | Record<string, unknown>;

  constructor(message: string, status: number, detail: Record<string, unknown>) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

export interface ProgressEvent {
  stage: string;
  progress: number;
}

const getBackendBase = () => {
  const HOST = import.meta.env.VITE_HOST;
  const backendPORT = import.meta.env.VITE_BACKEND_PORT;
  return `http://${HOST}:${backendPORT}`;
}

const baseURL = (): { url: string; id: string } => {
  const base = getBackendBase();
  const ID = crypto.randomUUID();
  return { url: `${base}/backend/upload/${ID}`, id: ID };
}

/** Read a File as a base64 data URL string (e.g., "data:image/png;base64,...") */
const getBase64 = (data: File): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.readAsDataURL(data);
    reader.onload = () => {resolve(reader.result as string)};
    reader.onerror = (error) => {reject(error)};
  });
}

export const UPLOAD_TIMEOUT_MS = 5 * 60 * 1000; // 5 minutes

export interface CustomParams {
  colormode?: string;
  mode?: string;
  filter_speckle?: number;
  color_precision?: number;
  layer_difference?: number;
  corner_threshold?: number;
  length_threshold?: number;
  max_iterations?: number;
  splice_threshold?: number;
  path_precision?: number;
}

/**
 * Send a file to the backend upload endpoint.
 * Encodes the file as base64, attaches an AbortController for timeout,
 * and parses error responses into ApiError instances.
 */
const doPost = async (url: string, data: File, preset: string = 'balanced', customParams?: CustomParams): Promise<ApiResponse> => {
  const name = data.name;
  const base64 = await getBase64(data);
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), UPLOAD_TIMEOUT_MS);

  const body: Record<string, unknown> = { name, data: base64, preset };
  if (customParams) {
    body.custom_params = customParams;
  }

  let response: Response;
  try {
    response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError('Request timed out', 0, { error: 'Upload timed out. The file may be too large or the server is unresponsive.' });
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }

  if (!response.ok) {
    let detail: Record<string, unknown> = {};
    try {
      const errorBody = await response.json();
      detail = errorBody.detail || errorBody;
    } catch {
      detail = { error: response.statusText };
    }
    throw new ApiError(response.statusText, response.status, detail);
  }

  return await response.json() as ApiResponse;
}

/**
 * Upload a file for conversion with optional SSE progress tracking.
 * Opens an EventSource to the progress endpoint before sending the POST,
 * so the client receives real-time stage/progress updates during conversion.
 */
export const Post = async (
  data: File,
  preset: string = 'balanced',
  onProgress?: (event: ProgressEvent) => void,
  customParams?: CustomParams,
): Promise<ApiResponse> => {
  const { url, id } = baseURL();
  let eventSource: EventSource | null = null;

  try {
    // Start SSE progress listener if callback provided
    if (onProgress) {
      const progressUrl = `${getBackendBase()}/backend/progress/${id}`;
      eventSource = new EventSource(progressUrl);
      eventSource.onmessage = (e) => {
        try {
          const progress = JSON.parse(e.data) as ProgressEvent;
          onProgress(progress);
        } catch {
          // ignore parse errors
        }
      };
      eventSource.onerror = () => {
        eventSource?.close();
        eventSource = null;
      };
    }

    const response = await doPost(url, data, preset, customParams);
    return response;
  } catch (error: unknown) {
    if (error instanceof ApiError) {
      throw error;
    }
    const message = error instanceof Error ? error.message : 'Network error';
    throw new ApiError(message, 0, { error: 'Failed to connect to server' });
  } finally {
    eventSource?.close();
  }
}
