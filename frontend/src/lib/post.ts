const generateUUID = () => {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
      const r = Math.random() * 16 | 0;
      const v = c === 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
  });
}

const baseURL = () => {
  const HOST = import.meta.env.VITE_HOST;
  const backendPORT = import.meta.env.VITE_BACKEND_PORT;
  const ID = generateUUID();
  return `http://${HOST}:${backendPORT}/backend/upload/${ID}`;
}

/** Result type for the Post function */
export type PostResult =
  | { success: true; url: string }
  | { success: false; error: string };

const getBase64 = async (data: File): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.readAsDataURL(data);
    reader.onload = () => {resolve(reader.result as string)};
    reader.onerror = (error) => {reject(error)};
  });
}

const doPost = async (url: string, data: File): Promise<PostResult> => {
  try {
    const name = data.name;
    const base64 = await getBase64(data);
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ name: name, data: base64 }),
    });

    if (!response.ok) {
      return {
        success: false,
        error: `Server error: ${response.status} ${response.statusText}`,
      };
    }

    const json = await response.json();
    return { success: true, url: json.url };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Unknown error';
    return { success: false, error: `Network error: ${message}` };
  }
}

export const Post = async (data: File): Promise<PostResult> => {
  const url = baseURL();
  return doPost(url, data);
}
