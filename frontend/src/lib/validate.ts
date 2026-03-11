export const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
export const VALID_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif'];

export function validateFile(file: File): string | null {
  const lowerName = file.name.toLowerCase();
  const hasValidExtension = VALID_EXTENSIONS.some(ext => lowerName.endsWith(ext));

  if (!hasValidExtension) {
    return 'Supported formats: PNG, JPG/JPEG, WebP, BMP, GIF';
  }

  if (file.size > MAX_FILE_SIZE) {
    return `File size exceeds ${MAX_FILE_SIZE / (1024 * 1024)}MB limit`;
  }

  return null;
}
