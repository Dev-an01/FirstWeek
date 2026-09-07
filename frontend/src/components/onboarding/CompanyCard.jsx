/**
 * CompanyCard Component (Memoized)
 *
 * Displays a company summary card in the grid view.
 */

import { memo, useCallback } from 'react';
import PropTypes from 'prop-types';
import { Building2, Users, FileText } from 'lucide-react';
import { StatusBadge } from './StatusBadge';

function CompanyCardComponent({ company, onClick }) {
  const handleClick = useCallback(() => {
    onClick(company.id);
  }, [company.id, onClick]);

  // Determine status based on executives count and profile status
  const getStatus = () => {
    if (!company.executives_count && company.executives_count !== 0) return 'pending';
    if (company.executives_count === 0) return 'pending';
    // Could add more logic here based on executive calibration status
    return 'ready';
  };

  return (
    <div
      onClick={handleClick}
      className="
        bg-white rounded-xl p-5 shadow-sm border border-gray-100
        hover:shadow-md hover:border-primary/20
        transition-all duration-200 cursor-pointer
        active:scale-[0.98]
      "
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="p-2.5 bg-primary-light rounded-lg">
          <Building2 className="w-5 h-5 text-primary" />
        </div>
        <StatusBadge status={getStatus()} />
      </div>

      {/* Company Info */}
      <h3 className="font-semibold text-gray-900 mb-1 truncate">
        {company.name}
      </h3>
      <p className="text-sm text-gray-500 mb-4 truncate">
        {company.industry || 'No industry specified'}
      </p>

      {/* Stats */}
      <div className="flex items-center gap-4 text-sm text-gray-600">
        <span className="flex items-center gap-1.5">
          <Users className="w-4 h-4" />
          <span>{company.executives_count || 0} executives</span>
        </span>
        {company.kb_doc_count !== undefined && (
          <span className="flex items-center gap-1.5">
            <FileText className="w-4 h-4" />
            <span>{company.kb_doc_count} KB docs</span>
          </span>
        )}
      </div>
    </div>
  );
}

CompanyCardComponent.propTypes = {
  company: PropTypes.shape({
    id: PropTypes.string.isRequired,
    name: PropTypes.string.isRequired,
    industry: PropTypes.string,
    executives_count: PropTypes.number,
    kb_doc_count: PropTypes.number,
  }).isRequired,
  onClick: PropTypes.func.isRequired,
};

export const CompanyCard = memo(CompanyCardComponent);
export default CompanyCard;
