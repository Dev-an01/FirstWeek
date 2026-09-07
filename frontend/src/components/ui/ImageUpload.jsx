import { useState, useRef } from 'react';
import { Camera, Upload, X, Loader } from 'lucide-react';

/**
 * ImageUpload Component
 * Allows users to upload and preview images
 * Converts images to base64 for easy transmission
 */
export function ImageUpload({
  currentImage,
  onImageChange,
  disabled = false,
  maxSizeInMB = 5,
  accept = 'image/*',
}) {
  const [preview, setPreview] = useState(currentImage || null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const fileInputRef = useRef(null);

  /**
   * Convert file to base64
   */
  const fileToBase64 = (file) => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.readAsDataURL(file);
      reader.onload = () => resolve(reader.result);
      reader.onerror = (err) => reject(err);
    });
  };

  /**
   * Handle file selection
   */
  const handleFileChange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setError(null);
    setIsLoading(true);

    try {
      // Validate file type
      if (!file.type.startsWith('image/')) {
        throw new Error('Please select an image file');
      }

      // Validate file size
      const maxSizeInBytes = maxSizeInMB * 1024 * 1024;
      if (file.size > maxSizeInBytes) {
        throw new Error(`Image size must be less than ${maxSizeInMB}MB`);
      }

      // Convert to base64
      const base64 = await fileToBase64(file);

      // Set preview
      setPreview(base64);

      // Call parent callback
      onImageChange(base64);
    } catch (err) {
      setError(err.message);
      setPreview(currentImage);
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Handle remove image
   */
  const handleRemove = () => {
    setPreview(null);
    setError(null);
    onImageChange(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  /**
   * Trigger file input click
   */
  const handleClick = () => {
    if (!disabled && !isLoading) {
      fileInputRef.current?.click();
    }
  };

  return (
    <div className="flex flex-col items-center gap-4">
      {/* Image Preview */}
      <div className="relative">
        <div
          className={`w-32 h-32 rounded-full overflow-hidden border-4 border-gray-200 bg-gray-100 flex items-center justify-center ${
            !disabled && !isLoading
              ? 'cursor-pointer hover:border-primary transition-colors'
              : ''
          }`}
          onClick={handleClick}
        >
          {isLoading ? (
            <Loader className="animate-spin text-primary" size={32} />
          ) : preview ? (
            <img
              src={preview}
              alt="Profile preview"
              className="w-full h-full object-cover"
            />
          ) : (
            <Camera className="text-gray-400" size={32} />
          )}
        </div>

        {/* Remove button */}
        {preview && !disabled && !isLoading && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              handleRemove();
            }}
            className="absolute top-0 right-0 bg-red-500 text-white rounded-full p-1 hover:bg-red-600 transition-colors shadow-lg"
            title="Remove image"
          >
            <X size={16} />
          </button>
        )}

        {/* Upload button overlay */}
        {!disabled && !isLoading && (
          <button
            type="button"
            onClick={handleClick}
            className="absolute bottom-0 right-0 bg-primary text-white rounded-full p-2 hover:bg-primary-dark transition-colors shadow-lg"
            title="Upload image"
          >
            <Upload size={16} />
          </button>
        )}
      </div>

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept={accept}
        onChange={handleFileChange}
        className="hidden"
        disabled={disabled || isLoading}
      />

      {/* Instructions */}
      <div className="text-center">
        <p className="text-sm text-gray-600">
          {preview ? 'Click to change image' : 'Click to upload image'}
        </p>
        <p className="text-xs text-gray-500 mt-1">
          Max size: {maxSizeInMB}MB • Supported: JPG, PNG, GIF, WEBP
        </p>
      </div>

      {/* Error message */}
      {error && (
        <div className="text-sm text-red-600 bg-red-50 px-3 py-2 rounded-lg border border-red-200">
          {error}
        </div>
      )}
    </div>
  );
}
