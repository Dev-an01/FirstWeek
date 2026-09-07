/**
 * StatusBadge Component (Memoized)
 *
 * Displays status indicators with consistent styling.
 */

import { memo } from 'react';
import PropTypes from 'prop-types';

const statusConfig = {
  // Document statuses
  pending: { bg: 'bg-gray-100', text: 'text-gray-600', label: 'Pending' },
  uploading: { bg: 'bg-blue-100', text: 'text-blue-600', label: 'Uploading...' },
  processing: { bg: 'bg-yellow-100', text: 'text-yellow-700', label: 'Processing...' },
  processed: { bg: 'bg-green-100', text: 'text-green-600', label: 'Processed' },

  // Executive/Profile statuses
  calibrating: { bg: 'bg-blue-100', text: 'text-blue-600', label: 'Calibrating...' },
  calibrated: { bg: 'bg-green-100', text: 'text-green-600', label: 'Ready' },
  ready: { bg: 'bg-green-100', text: 'text-green-600', label: 'Ready' },

  // Job statuses
  parsing: { bg: 'bg-yellow-100', text: 'text-yellow-700', label: 'Parsing...' },
  extracting: { bg: 'bg-yellow-100', text: 'text-yellow-700', label: 'Extracting...' },
  assembling: { bg: 'bg-yellow-100', text: 'text-yellow-700', label: 'Assembling...' },
  validating: { bg: 'bg-yellow-100', text: 'text-yellow-700', label: 'Validating...' },
  deploying: { bg: 'bg-yellow-100', text: 'text-yellow-700', label: 'Deploying...' },
  embedding: { bg: 'bg-yellow-100', text: 'text-yellow-700', label: 'Embedding...' },
  completed: { bg: 'bg-green-100', text: 'text-green-600', label: 'Completed' },

  // Error
  failed: { bg: 'bg-red-100', text: 'text-red-600', label: 'Failed' },
  error: { bg: 'bg-red-100', text: 'text-red-600', label: 'Error' },
};

function StatusBadgeComponent({ status, label, size = 'sm', className = '' }) {
  const config = statusConfig[status?.toLowerCase()] || statusConfig.pending;
  const displayLabel = label || config.label;

  const sizeClasses = {
    xs: 'px-1.5 py-0.5 text-xs',
    sm: 'px-2 py-1 text-xs',
    md: 'px-2.5 py-1 text-sm',
  };

  return (
    <span
      className={`
        inline-flex items-center rounded-full font-medium
        ${config.bg} ${config.text}
        ${sizeClasses[size] || sizeClasses.sm}
        ${className}
      `}
    >
      {/* Animated dot for in-progress statuses */}
      {['uploading', 'processing', 'calibrating', 'parsing', 'extracting', 'assembling', 'validating', 'deploying', 'embedding'].includes(status?.toLowerCase()) && (
        <span className="w-1.5 h-1.5 mr-1.5 rounded-full bg-current animate-pulse" />
      )}
      {displayLabel}
    </span>
  );
}

StatusBadgeComponent.propTypes = {
  status: PropTypes.string,
  label: PropTypes.string,
  size: PropTypes.oneOf(['xs', 'sm', 'md']),
  className: PropTypes.string,
};

export const StatusBadge = memo(StatusBadgeComponent);
export default StatusBadge;
