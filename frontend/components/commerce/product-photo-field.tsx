'use client';

import { useEffect, useId, useRef, useState } from 'react';
import { uploadStagedProductMedia } from '@/lib/api/commerce';
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

function shouldPreferNativeCapture() {
  if (typeof window === 'undefined' || typeof navigator === 'undefined') {
    return false;
  }
  const coarsePointer = window.matchMedia?.('(pointer: coarse)').matches ?? false;
  const touchDevice = navigator.maxTouchPoints > 0;
  const mobileUserAgent = /android|iphone|ipad|ipod/i.test(navigator.userAgent);
  return coarsePointer || touchDevice || mobileUserAgent;
}

function supportsDirectCamera() {
  return (
    typeof window !== 'undefined'
    && window.isSecureContext
    && typeof navigator !== 'undefined'
    && Boolean(navigator.mediaDevices?.getUserMedia)
  );
}

function cameraErrorMessage(error: unknown) {
  if (!(error instanceof Error)) {
    return 'Unable to open camera. Use device capture fallback below.';
  }
  const name = (error as DOMException).name;
  if (name === 'NotAllowedError' || name === 'SecurityError') {
    return 'Camera permission was blocked. Allow camera access in browser settings, or use device capture fallback below.';
  }
  if (name === 'NotFoundError' || name === 'OverconstrainedError') {
    return 'No suitable camera was found on this device. Use device capture fallback below.';
  }
  if (name === 'NotReadableError') {
    return 'Camera is already in use by another app. Close other apps and try again, or use device capture fallback.';
  }
  return error.message || 'Unable to open camera. Use device capture fallback below.';
}

async function waitForVideoElement(
  ref: { current: HTMLVideoElement | null },
  attempts = 12,
  delayMs = 40,
): Promise<HTMLVideoElement | null> {
  for (let index = 0; index < attempts; index += 1) {
    if (ref.current) {
      return ref.current;
    }
    await new Promise((resolve) => window.setTimeout(resolve, delayMs));
  }
  return ref.current;
}

export function ProductPhotoField({ image, onUploaded, onRemove }: ProductPhotoFieldProps) {
  const uploadId = useId();
  const fallbackCaptureId = useId();
  const uploadRef = useRef<HTMLInputElement | null>(null);
  const fallbackCaptureRef = useRef<HTMLInputElement | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const [error, setError] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const [isCameraOpen, setIsCameraOpen] = useState(false);
  const [isStartingCamera, setIsStartingCamera] = useState(false);
  const [cameraReady, setCameraReady] = useState(false);

  const preferNativeCapture = shouldPreferNativeCapture();
  const canUseDirectCamera = supportsDirectCamera();

  const stopCamera = () => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (videoRef.current) {
      videoRef.current.pause();
      videoRef.current.srcObject = null;
      videoRef.current.removeAttribute('src');
      videoRef.current.load();
    }
    setCameraReady(false);
  };

  useEffect(() => () => stopCamera(), []);

  const triggerNativeCapture = () => {
    if (isUploading) {
      return;
    }
    const input = fallbackCaptureRef.current;
    if (!input) {
      return;
    }
    input.value = '';
    if (typeof input.showPicker === 'function') {
      try {
        input.showPicker();
        return;
      } catch {
        // Ignore and use click fallback.
      }
    }
    input.click();
  };

  useEffect(() => {
    if (!isCameraOpen) {
      stopCamera();
      return;
    }

    if (!canUseDirectCamera) {
      setIsStartingCamera(false);
      setCameraReady(false);
      setError('Direct camera preview is not available in this browser. Use device capture fallback below.');
      return;
    }

    let cancelled = false;
    let readyTimer: number | null = null;

    const startCamera = async () => {
      setError('');
      setIsStartingCamera(true);
      setCameraReady(false);

      const video = await waitForVideoElement(videoRef);
      if (cancelled) {
        return;
      }
      if (!video) {
        setIsStartingCamera(false);
        setError('Camera preview could not initialize. Use device capture fallback below.');
        return;
      }

      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: {
            facingMode: { ideal: 'environment' },
            width: { ideal: 1280 },
            height: { ideal: 1280 },
          },
          audio: false,
        });

        if (cancelled) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }

        streamRef.current = stream;

        let readyMarked = false;
        const markReady = () => {
          if (cancelled || readyMarked) {
            return;
          }
          if (video.videoWidth > 0 && video.videoHeight > 0) {
            readyMarked = true;
            setCameraReady(true);
            setIsStartingCamera(false);
          }
        };

        const eventNames: Array<keyof HTMLMediaElementEventMap> = ['loadedmetadata', 'loadeddata', 'canplay', 'playing'];
        eventNames.forEach((eventName) => {
          video.addEventListener(eventName, markReady);
        });

        video.muted = true;
        video.autoplay = true;
        video.playsInline = true;
        video.setAttribute('playsinline', 'true');
        video.setAttribute('webkit-playsinline', 'true');
        video.srcObject = stream;

        try {
          await video.play();
        } catch {
          // Some browsers reject play() while metadata events still fire.
        }

        markReady();

        readyTimer = window.setTimeout(() => {
          if (cancelled || readyMarked) {
            return;
          }
          setIsStartingCamera(false);
          setError('Live camera preview is unavailable. Use device capture fallback below.');
        }, 2800);

        return () => {
          eventNames.forEach((eventName) => {
            video.removeEventListener(eventName, markReady);
          });
        };
      } catch (cameraError) {
        if (cancelled) {
          return;
        }
        setIsStartingCamera(false);
        setCameraReady(false);
        setError(cameraErrorMessage(cameraError));
      }
      return undefined;
    };

    let detachListeners: (() => void) | undefined;
    void (async () => {
      detachListeners = await startCamera();
    })();

    return () => {
      cancelled = true;
      if (readyTimer) {
        window.clearTimeout(readyTimer);
      }
      detachListeners?.();
      stopCamera();
    };
  }, [isCameraOpen, canUseDirectCamera]);

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
      setIsCameraOpen(false);
    } catch (uploadError) {
      setError(
        uploadError instanceof Error
          ? uploadError.message
          : 'Unable to upload product photo. Try a smaller image or capture a new photo.',
      );
    } finally {
      setIsUploading(false);
      if (uploadRef.current) uploadRef.current.value = '';
      if (fallbackCaptureRef.current) fallbackCaptureRef.current.value = '';
    }
  };

  const captureFromCamera = async () => {
    const video = videoRef.current;
    if (!video) {
      setError('Camera preview is not ready yet. Use device capture fallback below.');
      return;
    }
    if (!cameraReady || !streamRef.current?.active || !video.videoWidth || !video.videoHeight) {
      setError('Camera preview is not ready yet. Use device capture fallback below.');
      return;
    }

    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const context = canvas.getContext('2d');
    if (!context) {
      setError('Unable to capture this photo right now.');
      return;
    }

    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise<Blob | null>((resolve) => {
      canvas.toBlob(resolve, 'image/jpeg', 0.9);
    });
    if (!blob) {
      setError('Unable to capture this photo right now.');
      return;
    }

    const capturedFile = new File([blob], `capture-${Date.now()}.jpg`, {
      type: 'image/jpeg',
      lastModified: Date.now(),
    });

    await uploadFile(capturedFile);
  };

  const openCapture = () => {
    if (preferNativeCapture || !canUseDirectCamera) {
      triggerNativeCapture();
      return;
    }
    setError('');
    setIsCameraOpen(true);
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
          {preferNativeCapture || !canUseDirectCamera ? (
            <label className={`button-like${isUploading ? ' disabled' : ''}`} htmlFor={fallbackCaptureId} aria-disabled={isUploading}>
              Capture photo
            </label>
          ) : (
            <button type="button" onClick={openCapture} disabled={isUploading}>
              Capture photo
            </button>
          )}
          <input
            ref={fallbackCaptureRef}
            id={fallbackCaptureId}
            type="file"
            accept="image/*"
            capture="environment"
            className="visually-hidden"
            onChange={(event) => void uploadFile(event.target.files?.[0] ?? null)}
          />

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

      {isCameraOpen ? (
        <div className="product-photo-camera-modal" role="dialog" aria-modal="true" aria-label="Capture product photo">
          <div className="product-photo-camera-card">
            <div className="product-photo-camera-head">
              <strong>Capture product photo</strong>
              <button type="button" className="secondary" onClick={() => setIsCameraOpen(false)} disabled={isUploading}>
                Close
              </button>
            </div>

            <div className="product-photo-camera-preview">
              {isStartingCamera ? (
                <div className="product-photo-camera-placeholder">Opening camera…</div>
              ) : (
                <video ref={videoRef} autoPlay playsInline muted />
              )}
            </div>

            {!cameraReady ? (
              <div className="product-photo-camera-fallback">
                <p className="workspace-helper-copy">
                  If live preview is unavailable, use device capture below.
                </p>
                <label className={`button-like${isUploading ? ' disabled' : ''}`} htmlFor={fallbackCaptureId} aria-disabled={isUploading}>
                  Use device capture
                </label>
              </div>
            ) : null}

            {error ? <p className="workspace-error-copy">{error}</p> : null}

            <div className="product-photo-camera-actions">
              <button type="button" onClick={() => setIsCameraOpen(false)} className="secondary" disabled={isUploading}>
                Cancel
              </button>
              <button type="button" className="btn-primary" onClick={() => void captureFromCamera()} disabled={isUploading || isStartingCamera}>
                {isUploading ? 'Saving…' : 'Use this photo'}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
