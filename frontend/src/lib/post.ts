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

const getBase64 = async (data: any) => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.readAsDataURL(data);
    reader.onload = () => {resolve(reader.result)};
    reader.onerror = (error) => {reject(error)};
  });
}

const doPost = async (url: string, data: any) => {
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
    };
  }

  return result;
}

export const Post = async (data: any) => {
  try {
    const url = baseURL();
    const response = await doPost(url, data);
    return response;
  } catch (error: any) {
    // Re-throw with more context
    throw {
      message: error.message || 'Network error',
      detail: error.detail || { error: 'Failed to connect to server' }
    };
  }
}

