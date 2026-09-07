/**
 * ExecutiveRow Component (Memoized)
 *
 * Displays an executive row with hierarchy indentation.
 */

import { memo, useCallback } from 'react';
import PropTypes from 'prop-types';
import { User, ChevronRight, FileText } from 'lucide-react';
import { StatusBadge } from './StatusBadge';

function ExecutiveRowComponent({ executive, onClick, indentLevel = 0 }) {
  const handleClick = useCallback(() => {
    onClick(executive.id);
  }, [executive.id, onClick]);

  // Determine status
  const getStatus = () => {
    if (executive.has_profile && executive.has_voiceprint) return 'ready';
    if (executive.has_profile || executive.has_voiceprint) return 'processing';
    return 'pending';
  };

  // Count documents if available
  const docCount = executive.documents?.length || executive.doc_count || 0;

  return (
    <div
      onClick={handleClick}
      className="
        flex items-center justify-between p-3 rounded-lg
        bg-gray-50 hover:bg-gray-100
        transition-colors duration-150 cursor-pointer
        active:scale-[0.99]
      "
      style={{ marginLeft: indentLevel * 24 }}
    >
      {/* Left: Avatar + Info */}
      <div className="flex items-center gap-3 min-w-0 flex-1">
        {/* Hierarchy connector */}
        {indentLevel > 0 && (
          <div className="w-4 h-px bg-gray-300 -ml-4" />
        )}

        {/* Avatar */}
        <div className="w-9 h-9 rounded-full bg-primary-light flex items-center justify-center flex-shrink-0">
          <User className="w-5 h-5 text-primary" />
        </div>

        {/* Info */}
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-gray-900 truncate">
            {executive.name}
            {executive.name_english && executive.name !== executive.name_english && (
              <span className="text-gray-400 font-normal ml-1">
                ({executive.name_english})
              </span>
            )}
          </p>
          <p className="text-xs text-gray-500 truncate">
            {executive.title || 'No title'}
          </p>
        </div>
      </div>

      {/* Right: Stats + Status + Arrow */}
      <div className="flex items-center gap-3 flex-shrink-0 ml-3">
        {/* Doc count */}
        {docCount > 0 && (
          <span className="flex items-center gap-1 text-xs text-gray-500">
            <FileText className="w-3.5 h-3.5" />
            {docCount}
          </span>
        )}

        {/* Status */}
        <StatusBadge status={getStatus()} size="xs" />

        {/* Arrow */}
        <ChevronRight className="w-4 h-4 text-gray-400" />
      </div>
    </div>
  );
}

ExecutiveRowComponent.propTypes = {
  executive: PropTypes.shape({
    id: PropTypes.string.isRequired,
    name: PropTypes.string.isRequired,
    name_english: PropTypes.string,
    title: PropTypes.string,
    has_profile: PropTypes.bool,
    has_voiceprint: PropTypes.bool,
    documents: PropTypes.array,
    doc_count: PropTypes.number,
    hierarchy_level: PropTypes.number,
    reports_to: PropTypes.string,
  }).isRequired,
  onClick: PropTypes.func.isRequired,
  indentLevel: PropTypes.number,
};

export const ExecutiveRow = memo(ExecutiveRowComponent);
export default ExecutiveRow;
