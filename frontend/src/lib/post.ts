const generateUUID = () => {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
      const r = Math.random() * 16 | 0;
      const v = c === 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
  });
}

const baseURL = () => {
  const ID = generateUUID();
  return `http://localhost:3000/api/vi/${ID}`;
}

const doPost = async (url: string, data: any) => {
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });
  return response.json();
}

export const Post = async (data: any) => {
  const url = baseURL();
  console.log(url);
  const response = await doPost(url, data);
  return response;
}

