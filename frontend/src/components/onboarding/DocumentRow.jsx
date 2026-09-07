/**
 * DocumentRow Component (Memoized)
 *
 * Displays a document row with status and delete action.
 */

import { memo, useCallback } from 'react';
import PropTypes from 'prop-types';
import { FileText, Trash2, Loader2, RotateCcw } from 'lucide-react';
import { StatusBadge } from './StatusBadge';

function DocumentRowComponent({ document, onDelete, onRestore, showRestore = false }) {
  const handleDelete = useCallback(
    (e) => {
      e.stopPropagation();
      if (onDelete) onDelete(document.id);
    },
    [document.id, onDelete]
  );

  const handleRestore = useCallback(
    (e) => {
      e.stopPropagation();
      if (onRestore) onRestore(document.id);
    },
    [document.id, onRestore]
  );

  const isUploading = document.status === 'uploading' || document._optimistic;
  const isInactive = document.is_active === false;

  // Format file size
  const formatSize = (bytes) => {
    if (!bytes) return '';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  // Get file icon color based on type
  const getFileIconClass = () => {
    const ext = document.filename?.split('.').pop()?.toLowerCase();
    switch (ext) {
      case 'pdf':
        return 'text-red-400';
      case 'docx':
      case 'doc':
        return 'text-blue-400';
      case 'txt':
        return 'text-gray-400';
      case 'json':
        return 'text-yellow-500';
      case 'png':
      case 'jpg':
      case 'jpeg':
        return 'text-green-400';
      default:
        return 'text-gray-400';
    }
  };

  return (
    <div
      className={`
        flex items-center justify-between p-3 rounded-lg
        ${isInactive ? 'bg-gray-100 opacity-60' : 'bg-gray-50'}
        ${isUploading ? 'animate-pulse' : ''}
      `}
    >
      {/* Left: Icon + Info */}
      <div className="flex items-center gap-3 min-w-0 flex-1">
        {isUploading ? (
          <Loader2 className="w-5 h-5 text-blue-500 animate-spin flex-shrink-0" />
        ) : (
          <FileText className={`w-5 h-5 flex-shrink-0 ${getFileIconClass()}`} />
        )}

        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-gray-900 truncate">
            {document.filename}
          </p>
          <p className="text-xs text-gray-500">
            {formatSize(document.file_size)}
            {document.text_length > 0 && ` • ${document.text_length.toLocaleString()} chars`}
          </p>
        </div>
      </div>

      {/* Right: Status + Actions */}
      <div className="flex items-center gap-3 flex-shrink-0 ml-3">
        <StatusBadge
          status={isUploading ? 'uploading' : isInactive ? 'pending' : 'processed'}
          size="xs"
        />

        {!isUploading && (
          <>
            {isInactive && showRestore && onRestore ? (
              <button
                onClick={handleRestore}
                className="p-1.5 text-gray-400 hover:text-green-500 transition-colors rounded hover:bg-green-50"
                title="Restore document"
              >
                <RotateCcw className="w-4 h-4" />
              </button>
            ) : (
              onDelete && (
                <button
                  onClick={handleDelete}
                  className="p-1.5 text-gray-400 hover:text-red-500 transition-colors rounded hover:bg-red-50"
                  title="Delete document"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              )
            )}
          </>
        )}
      </div>
    </div>
  );
}

DocumentRowComponent.propTypes = {
  document: PropTypes.shape({
    id: PropTypes.string.isRequired,
    filename: PropTypes.string.isRequired,
    file_size: PropTypes.number,
    text_length: PropTypes.number,
    content_type: PropTypes.string,
    status: PropTypes.string,
    is_active: PropTypes.bool,
    _optimistic: PropTypes.bool,
  }).isRequired,
  onDelete: PropTypes.func,
  onRestore: PropTypes.func,
  showRestore: PropTypes.bool,
};

export const DocumentRow = memo(DocumentRowComponent);
export default DocumentRow;
