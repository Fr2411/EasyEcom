'use client';

import { useId, useRef, useState } from 'react';
import { uploadStagedProductMedia } from '@/lib/api/commerce';
import type { ProductMedia } from '@/types/catalog';

type ProductPhotoFieldProps = {
  image: ProductMedia | null;
  onUploaded: (image: ProductMedia) => void;
  onRemove: () => void;
};

export function ProductPhotoField({ image, onUploaded, onRemove }: ProductPhotoFieldProps) {
  const uploadId = useId();
  const captureId = useId();
  const uploadRef = useRef<HTMLInputElement | null>(null);
  const captureRef = useRef<HTMLInputElement | null>(null);
  const [error, setError] = useState('');
  const [isUploading, setIsUploading] = useState(false);

  const uploadFile = async (file: File | null) => {
    if (!file) {
      return;
    }
    setError('');
    setIsUploading(true);
    try {
      const uploaded = await uploadStagedProductMedia(file);
      onUploaded(uploaded);
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : 'Unable to upload product photo.');
    } finally {
      setIsUploading(false);
      if (uploadRef.current) uploadRef.current.value = '';
      if (captureRef.current) captureRef.current.value = '';
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
          <button type="button" onClick={() => uploadRef.current?.click()} disabled={isUploading}>
            {isUploading ? 'Uploading…' : image ? 'Replace photo' : 'Upload photo'}
          </button>

          <input
            ref={captureRef}
            id={captureId}
            type="file"
            accept="image/*"
            capture="environment"
            className="visually-hidden"
            onChange={(event) => void uploadFile(event.target.files?.[0] ?? null)}
          />
          <button type="button" onClick={() => captureRef.current?.click()} disabled={isUploading}>
            Capture photo
          </button>

          {image ? (
            <button type="button" onClick={onRemove} disabled={isUploading}>
              Remove photo
            </button>
          ) : null}
        </div>
        <p className="workspace-helper-copy">
          Upload or capture one primary product photo. EasyEcom stores a 768×768 large image for AI and a 256×256 thumbnail for the UI.
        </p>
        {error ? <p className="workspace-error-copy">{error}</p> : null}
      </div>
    </div>
  );
}
