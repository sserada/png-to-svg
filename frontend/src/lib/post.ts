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

const getBase64 = (data: File): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.readAsDataURL(data);
    reader.onload = () => {resolve(reader.result as string)};
    reader.onerror = (error) => {reject(error)};
  });
}

const doPost = async (url: string, data: File, preset: string = 'balanced'): Promise<ApiResponse> => {
  const name = data.name;
  const base64 = await getBase64(data);
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ name : name, data : base64, preset }),
  });

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

export const Post = async (
  data: File,
  preset: string = 'balanced',
  onProgress?: (event: ProgressEvent) => void
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

    const response = await doPost(url, data, preset);
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
