import { describe, it, expect } from 'vitest';
import { validateFile } from '$lib/validate';

describe('validateFile', () => {
  it('should accept PNG files', () => {
    const file = new File(['test'], 'image.png', { type: 'image/png' });
    expect(validateFile(file)).toBeNull();
  });

  it('should accept JPG files', () => {
    const file = new File(['test'], 'image.jpg', { type: 'image/jpeg' });
    expect(validateFile(file)).toBeNull();
  });

  it('should accept JPEG files', () => {
    const file = new File(['test'], 'image.jpeg', { type: 'image/jpeg' });
    expect(validateFile(file)).toBeNull();
  });

  it('should accept WebP files', () => {
    const file = new File(['test'], 'image.webp', { type: 'image/webp' });
    expect(validateFile(file)).toBeNull();
  });

  it('should accept BMP files', () => {
    const file = new File(['test'], 'image.bmp', { type: 'image/bmp' });
    expect(validateFile(file)).toBeNull();
  });

  it('should accept GIF files', () => {
    const file = new File(['test'], 'image.gif', { type: 'image/gif' });
    expect(validateFile(file)).toBeNull();
  });

  it('should accept uppercase extensions', () => {
    const file = new File(['test'], 'image.PNG', { type: 'image/png' });
    expect(validateFile(file)).toBeNull();
  });

  it('should accept mixed case extensions', () => {
    const file = new File(['test'], 'image.JpEg', { type: 'image/jpeg' });
    expect(validateFile(file)).toBeNull();
  });

  it('should reject unsupported file types', () => {
    const file = new File(['test'], 'document.pdf', { type: 'application/pdf' });
    expect(validateFile(file)).toBe('Supported formats: PNG, JPG/JPEG, WebP, BMP, GIF');
  });

  it('should reject SVG files', () => {
    const file = new File(['test'], 'image.svg', { type: 'image/svg+xml' });
    expect(validateFile(file)).toBe('Supported formats: PNG, JPG/JPEG, WebP, BMP, GIF');
  });

  it('should reject TIFF files', () => {
    const file = new File(['test'], 'image.tiff', { type: 'image/tiff' });
    expect(validateFile(file)).toBe('Supported formats: PNG, JPG/JPEG, WebP, BMP, GIF');
  });

  it('should reject files exceeding 10MB', () => {
    const largeContent = new Uint8Array(11 * 1024 * 1024);
    const file = new File([largeContent], 'large.png', { type: 'image/png' });
    expect(validateFile(file)).toBe('File size exceeds 10MB limit');
  });

  it('should accept files exactly at 10MB', () => {
    const content = new Uint8Array(10 * 1024 * 1024);
    const file = new File([content], 'exact.png', { type: 'image/png' });
    expect(validateFile(file)).toBeNull();
  });

  it('should reject files with no extension', () => {
    const file = new File(['test'], 'noextension', { type: 'image/png' });
    expect(validateFile(file)).toBe('Supported formats: PNG, JPG/JPEG, WebP, BMP, GIF');
  });
});
