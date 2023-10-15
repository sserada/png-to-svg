const generateUUID = () => {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
      const r = Math.random() * 16 | 0;
      const v = c === 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
  });
}

const baseURL = () => {
  const ID = generateUUID();
  return `http://localhost:3000/backend/${ID}`;
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
  return response.json();
}

export const Post = async (data: any) => {
  const url = baseURL();
  const response = await doPost(url, data);
  return response;
}

