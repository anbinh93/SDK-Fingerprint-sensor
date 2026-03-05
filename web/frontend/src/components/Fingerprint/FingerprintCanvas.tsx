import { useEffect, useRef, useCallback } from 'react';
import './FingerprintCanvas.css';

interface FingerprintCanvasProps {
  imageData: string | null;  // base64 encoded grayscale image
  width?: number;
  height?: number;
  quality?: number;
  hasFinger?: boolean;
  size?: number;  // Display size in pixels
}

export function FingerprintCanvas({
  imageData,
  width = 192,
  height = 192,
  quality = 0,
  hasFinger = false,
  size = 250,
}: FingerprintCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const drawImage = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Clear canvas
    ctx.fillStyle = '#1a1a2e';
    ctx.fillRect(0, 0, size, size);

    if (!imageData) {
      // Draw placeholder
      ctx.fillStyle = '#2d3748';
      ctx.font = '14px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('No Image', size / 2, size / 2);
      return;
    }

    // Decode base64 to bytes
    try {
      const binaryString = atob(imageData);
      const bytes = new Uint8Array(binaryString.length);
      for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }

      // Create ImageData
      const imageDataObj = ctx.createImageData(width, height);
      const data = imageDataObj.data;

      // Convert grayscale to RGBA
      for (let i = 0; i < width * height; i++) {
        const gray = bytes[i] || 0;
        data[i * 4] = gray;      // R
        data[i * 4 + 1] = gray;  // G
        data[i * 4 + 2] = gray;  // B
        data[i * 4 + 3] = 255;   // A
      }

      // Create temporary canvas for scaling
      const tempCanvas = document.createElement('canvas');
      tempCanvas.width = width;
      tempCanvas.height = height;
      const tempCtx = tempCanvas.getContext('2d');
      if (tempCtx) {
        tempCtx.putImageData(imageDataObj, 0, 0);

        // Draw scaled to main canvas
        ctx.imageSmoothingEnabled = false;  // Keep pixelated look
        ctx.drawImage(tempCanvas, 0, 0, size, size);
      }
    } catch (e) {
      console.error('Failed to render fingerprint:', e);
      ctx.fillStyle = '#ef4444';
      ctx.font = '12px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('Render Error', size / 2, size / 2);
    }
  }, [imageData, width, height, size]);

  useEffect(() => {
    drawImage();
  }, [drawImage]);

  // Determine border color based on quality
  const getBorderClass = () => {
    if (!imageData) return '';
    if (hasFinger && quality > 20) return 'quality-good';
    if (hasFinger) return 'quality-medium';
    return 'quality-low';
  };

  return (
    <div className={`fingerprint-canvas-container ${getBorderClass()}`}>
      <canvas
        ref={canvasRef}
        width={size}
        height={size}
        className="fingerprint-canvas"
      />
      {imageData && (
        <div className="fingerprint-info">
          <span className={`finger-status ${hasFinger ? 'detected' : 'empty'}`}>
            {hasFinger ? 'Finger Detected' : 'No Finger'}
          </span>
          <span className="quality-score">
            Quality: {quality.toFixed(1)}
          </span>
        </div>
      )}
      {imageData && (
        <div className="quality-bar-container">
          <div
            className="quality-bar"
            style={{ width: `${Math.min(quality / 50 * 100, 100)}%` }}
          />
        </div>
      )}
    </div>
  );
}
