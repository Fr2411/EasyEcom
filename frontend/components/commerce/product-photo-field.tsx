'use client';

import { useId, useRef, useState } from 'react';
import { uploadStagedProductMedia } from '@/lib/api/commerce';
import { HoverHint } from '@/components/ui/hover-hint';
import type { ProductMedia } from '@/types/catalog';

type ProductPhotoFieldProps = {
  image: ProductMedia | null;
  onUploaded: (image: ProductMedia) => void | Promise<void>;
  onRemove: () => void;
};

const MAX_UPLOAD_EDGE = 2048;
const UPLOAD_QUALITY = 0.84;

async function loadImageElement(file: File) {
  const objectUrl = URL.createObjectURL(file);
  try {
    const image = await new Promise<HTMLImageElement>((resolve, reject) => {
      const element = new Image();
      element.onload = () => resolve(element);
      element.onerror = () => reject(new Error('Unable to read image file.'));
      element.src = objectUrl;
    });
    return image;
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}

async function normalizeUploadImage(file: File): Promise<File> {
  if (!file.type.startsWith('image/')) {
    return file;
  }
  const image = await loadImageElement(file);
  const scale = Math.min(1, MAX_UPLOAD_EDGE / Math.max(image.naturalWidth, image.naturalHeight));
  const width = Math.max(1, Math.round(image.naturalWidth * scale));
  const height = Math.max(1, Math.round(image.naturalHeight * scale));
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext('2d');
  if (!context) {
    return file;
  }
  context.fillStyle = '#ffffff';
  context.fillRect(0, 0, width, height);
  context.drawImage(image, 0, 0, width, height);
  const blob = await new Promise<Blob | null>((resolve) => {
    canvas.toBlob(resolve, 'image/jpeg', UPLOAD_QUALITY);
  });
  if (!blob) {
    return file;
  }
  return new File([blob], `${file.name.replace(/\.[^.]+$/, '') || 'product-photo'}.jpg`, {
    type: 'image/jpeg',
    lastModified: Date.now(),
  });
}

export function ProductPhotoField({ image, onUploaded, onRemove }: ProductPhotoFieldProps) {
  const uploadId = useId();
  const uploadRef = useRef<HTMLInputElement | null>(null);
  const [error, setError] = useState('');
  const [isUploading, setIsUploading] = useState(false);

  const uploadFile = async (file: File | null) => {
    if (!file) {
      return;
    }
    setError('');
    setIsUploading(true);
    try {
      const optimizedFile = await normalizeUploadImage(file);
      const uploaded = await uploadStagedProductMedia(optimizedFile);
      await onUploaded(uploaded);
    } catch (uploadError) {
      setError(
        uploadError instanceof Error
          ? uploadError.message
          : 'Unable to upload product photo. Try a smaller image.',
      );
    } finally {
      setIsUploading(false);
      if (uploadRef.current) uploadRef.current.value = '';
    }
  };

  return (
    <div className="product-photo-field">
      <div className="product-photo-preview">
        {image?.thumbnail_url ? (
          <img src={image.thumbnail_url} alt="Product preview" />
        ) : (
          <div className="product-photo-placeholder">No photo yet</div>
        )}
      </div>
      <div className="product-photo-actions">
        <div className="product-photo-buttons">
          <input
            ref={uploadRef}
            id={uploadId}
            type="file"
            accept="image/*"
            className="visually-hidden"
            onChange={(event) => void uploadFile(event.target.files?.[0] ?? null)}
          />
          <label className={`button-like${isUploading ? ' disabled' : ''}`} htmlFor={uploadId} aria-disabled={isUploading}>
            {isUploading ? 'Uploading…' : image ? 'Replace photo' : 'Upload photo'}
          </label>

          {image ? (
            <button type="button" onClick={onRemove} disabled={isUploading}>
              Remove photo
            </button>
          ) : null}
          <HoverHint
            label="Product photo help"
            text="Upload one primary product photo. EasyEcom stores a large image and a thumbnail for the UI."
          />
        </div>
        {error ? <p className="workspace-error-copy">{error}</p> : null}
      </div>
    </div>
  );
}
