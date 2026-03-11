interface ApiResponse {
  success: boolean;
  url: string;
  filename: string;
}

interface ApiError {
  status: number;
  message: string;
  detail: { error: string; code?: string } | Record<string, unknown>;
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

  const result = await response.json();

  // Check if the response indicates an error
  if (!response.ok) {
    throw {
      status: response.status,
      message: response.statusText,
      detail: result.detail || result
    } as ApiError;
  }

  return result as ApiResponse;
}

export const Post = async (
  data: File,
  preset: string = 'balanced',
  onProgress?: (event: ProgressEvent) => void
): Promise<ApiResponse> => {
  try {
    const { url, id } = baseURL();

    // Start SSE progress listener if callback provided
    let eventSource: EventSource | null = null;
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

    eventSource?.close();
    return response;
  } catch (error: unknown) {
    const apiError = error as ApiError;
    // Re-throw with more context
    throw {
      message: apiError.message || 'Network error',
      detail: apiError.detail || { error: 'Failed to connect to server' }
    };
  }
}
