/**
 * FileUploader Component
 *
 * Drag-and-drop file upload with preview.
 */

import { useState, useCallback, useRef } from 'react';
import PropTypes from 'prop-types';
import { Upload, X, FileText, AlertCircle } from 'lucide-react';
import { Button } from '../ui/Button';

const ACCEPTED_TYPES = '.pdf,.docx,.doc,.txt,.json,.png,.jpg,.jpeg';
const MAX_SIZE_MB = 50;
const MAX_FILES = 10;

const ACCESS_LEVELS = [
  { value: 'internal', label: 'Internal', description: 'Visible to employees and above' },
  { value: 'public', label: 'Public', description: 'Visible to everyone' },
  { value: 'executive', label: 'Executive', description: 'Visible to executives and admins' },
  { value: 'confidential', label: 'Confidential', description: 'Visible to admins only' },
];

export function FileUploader({
  onUpload,
  disabled = false,
  accept = ACCEPTED_TYPES,
  maxSizeMB = MAX_SIZE_MB,
  maxFiles = MAX_FILES,
  uploading = false,
  showAccessLevel = false,
}) {
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [errors, setErrors] = useState([]);
  const [accessLevel, setAccessLevel] = useState('internal');
  const inputRef = useRef(null);

  const validateFiles = useCallback(
    (files) => {
      const valid = [];
      const newErrors = [];

      Array.from(files).forEach((file) => {
        // Check max files
        if (selectedFiles.length + valid.length >= maxFiles) {
          newErrors.push(`Maximum ${maxFiles} files allowed`);
          return;
        }

        // Check file size
        if (file.size > maxSizeMB * 1024 * 1024) {
          newErrors.push(`${file.name} exceeds ${maxSizeMB}MB limit`);
          return;
        }

        // Check duplicates
        if (selectedFiles.some((f) => f.name === file.name && f.size === file.size)) {
          newErrors.push(`${file.name} already selected`);
          return;
        }

        valid.push(file);
      });

      if (newErrors.length > 0) {
        setErrors(newErrors);
        setTimeout(() => setErrors([]), 5000);
      }

      return valid;
    },
    [selectedFiles, maxSizeMB, maxFiles]
  );

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    if (!disabled) setIsDragging(true);
  }, [disabled]);

  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(false);

      if (disabled) return;

      const files = e.dataTransfer?.files;
      if (files) {
        const valid = validateFiles(files);
        setSelectedFiles((prev) => [...prev, ...valid]);
      }
    },
    [disabled, validateFiles]
  );

  const handleFileSelect = useCallback(
    (e) => {
      const files = e.target?.files;
      if (files) {
        const valid = validateFiles(files);
        setSelectedFiles((prev) => [...prev, ...valid]);
      }
      // Reset input so same file can be selected again
      if (inputRef.current) inputRef.current.value = '';
    },
    [validateFiles]
  );

  const removeFile = useCallback((index) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const clearFiles = useCallback(() => {
    setSelectedFiles([]);
    setErrors([]);
  }, []);

  const handleUpload = useCallback(async () => {
    if (selectedFiles.length === 0 || uploading) return;

    try {
      await onUpload(selectedFiles, { accessLevel });
      setSelectedFiles([]);
    } catch (error) {
      setErrors([error.message || 'Upload failed']);
    }
  }, [selectedFiles, uploading, onUpload, accessLevel]);

  const formatSize = (bytes) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="space-y-3">
      {/* Errors */}
      {errors.length > 0 && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
          <div className="flex items-start gap-2">
            <AlertCircle className="w-4 h-4 text-red-500 mt-0.5 flex-shrink-0" />
            <div className="text-sm text-red-600">
              {errors.map((error, i) => (
                <p key={i}>{error}</p>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Drop Zone */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => !disabled && inputRef.current?.click()}
        className={`
          relative border-2 border-dashed rounded-xl p-6 text-center
          transition-all duration-200
          ${isDragging ? 'border-primary bg-primary-light/50 scale-[1.01]' : 'border-gray-300'}
          ${disabled || uploading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer hover:border-primary hover:bg-gray-50'}
        `}
      >
        <Upload
          className={`w-10 h-10 mx-auto mb-3 ${isDragging ? 'text-primary' : 'text-gray-400'}`}
        />
        <p className="text-sm text-gray-600 mb-1">
          <span className="font-medium text-primary">Click to upload</span> or drag and drop
        </p>
        <p className="text-xs text-gray-400">
          PDF, DOCX, TXT, JSON, PNG, JPG (max {maxSizeMB}MB each, {maxFiles} files max)
        </p>

        <input
          ref={inputRef}
          type="file"
          multiple
          accept={accept}
          onChange={handleFileSelect}
          className="hidden"
          disabled={disabled || uploading}
        />
      </div>

      {/* Selected Files List */}
      {selectedFiles.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm text-gray-600">
            <span>{selectedFiles.length} file{selectedFiles.length > 1 ? 's' : ''} selected</span>
            <button
              onClick={clearFiles}
              className="text-gray-400 hover:text-gray-600"
              disabled={uploading}
            >
              Clear all
            </button>
          </div>

          <div className="space-y-1 max-h-40 overflow-y-auto">
            {selectedFiles.map((file, index) => (
              <div
                key={`${file.name}-${index}`}
                className="flex items-center justify-between p-2 bg-gray-50 rounded-lg"
              >
                <div className="flex items-center gap-2 min-w-0 flex-1">
                  <FileText className="w-4 h-4 text-gray-400 flex-shrink-0" />
                  <span className="text-sm text-gray-700 truncate">{file.name}</span>
                  <span className="text-xs text-gray-400 flex-shrink-0">
                    {formatSize(file.size)}
                  </span>
                </div>
                <button
                  onClick={() => removeFile(index)}
                  className="p-1 text-gray-400 hover:text-red-500 rounded"
                  disabled={uploading}
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>

          {showAccessLevel && (
            <div className="flex items-center gap-3 p-2 bg-gray-50 rounded-lg">
              <label className="text-sm font-medium text-gray-700 whitespace-nowrap">
                Access Level
              </label>
              <select
                value={accessLevel}
                onChange={(e) => setAccessLevel(e.target.value)}
                disabled={uploading}
                className="flex-1 text-sm border border-gray-300 rounded-md px-2 py-1.5 bg-white focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary"
              >
                {ACCESS_LEVELS.map((level) => (
                  <option key={level.value} value={level.value}>
                    {level.label} — {level.description}
                  </option>
                ))}
              </select>
            </div>
          )}

          <Button
            onClick={handleUpload}
            disabled={disabled || uploading || selectedFiles.length === 0}
            className="w-full"
          >
            {uploading ? 'Uploading...' : `Upload ${selectedFiles.length} file${selectedFiles.length > 1 ? 's' : ''}`}
          </Button>
        </div>
      )}
    </div>
  );
}

FileUploader.propTypes = {
  onUpload: PropTypes.func.isRequired,
  disabled: PropTypes.bool,
  accept: PropTypes.string,
  maxSizeMB: PropTypes.number,
  maxFiles: PropTypes.number,
  uploading: PropTypes.bool,
  showAccessLevel: PropTypes.bool,
};

export default FileUploader;
