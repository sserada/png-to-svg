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

const baseURL = (): string => {
  const HOST = import.meta.env.VITE_HOST;
  const backendPORT = import.meta.env.VITE_BACKEND_PORT;
  const ID = crypto.randomUUID();
  return `http://${HOST}:${backendPORT}/backend/upload/${ID}`;
}

const getBase64 = (data: File): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.readAsDataURL(data);
    reader.onload = () => {resolve(reader.result as string)};
    reader.onerror = (error) => {reject(error)};
  });
}

const doPost = async (url: string, data: File): Promise<ApiResponse> => {
  const name = data.name;
  const base64 = await getBase64(data);
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ name : name, data : base64 }),
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

export const Post = async (data: File): Promise<ApiResponse> => {
  try {
    const url = baseURL();
    const response = await doPost(url, data);
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
