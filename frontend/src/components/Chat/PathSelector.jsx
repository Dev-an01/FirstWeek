import { memo, useCallback, useMemo } from 'react';
import { X, Zap, Target, Brain, Sparkles } from 'lucide-react';
import PropTypes from 'prop-types';
import { Button } from '../ui/Button';

/**
 * PathSelector Component
 *
 * Modal for selecting LLM processing path (fast/standard/agentic)
 *
 * Features:
 * - Visual card-based selection
 * - Clear descriptions of each path
 * - Performance indicators
 * - Responsive design
 * - Keyboard navigation (ESC to close)
 * - Optimized with React.memo to prevent unnecessary re-renders
 */
function PathSelectorComponent({
  isOpen,
  onClose,
  selectedPath,
  onSelectPath,
}) {
  // Memoize paths array to prevent recreation on every render
  const paths = useMemo(
    () => [
      {
        id: '',
        name: 'Auto',
        subtitle: 'Smart Selection',
        icon: Sparkles,
        description:
          'AI automatically chooses the best processing path based on your query complexity.',
        performance: 'Optimized',
        color: 'from-purple-400 to-indigo-600',
        recommended: true,
      },
      {
        id: 'fast',
        name: 'Fast',
        subtitle: 'Simple Facts',
        icon: Zap,
        description:
          'Quick factual answers for straightforward questions. Best for "What is..." queries.',
        performance: '< 1.5s response',
        color: 'from-yellow-400 to-orange-500',
      },
      {
        id: 'standard',
        name: 'Standard',
        subtitle: 'Balanced Decisions',
        icon: Target,
        description:
          'Comprehensive recommendations and decision support. Best for "Should we..." queries.',
        performance: '< 2.5s response',
        color: 'from-blue-400 to-cyan-500',
      },
      {
        id: 'agentic',
        name: 'Agentic',
        subtitle: 'Complex Analysis',
        icon: Brain,
        description:
          'Deep analysis with multi-step reasoning. Best for "Compare..." or "Analyze..." queries.',
        performance: '< 5s response',
        color: 'from-pink-400 to-rose-600',
      },
    ],
    []
  );

  // Memoize handlers to prevent recreation
  const handlePathSelect = useCallback(
    (pathId) => {
      onSelectPath(pathId);
      onClose();
    },
    [onSelectPath, onClose]
  );

  const handleBackdropClick = useCallback(
    (e) => {
      if (e.target === e.currentTarget) {
        onClose();
      }
    },
    [onClose]
  );

  // Early return after all hooks
  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50 backdrop-blur-sm animate-fade-in"
      onClick={handleBackdropClick}
    >
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-hidden animate-scale-in">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">
              Select Query Path
            </h2>
            <p className="text-sm text-gray-600 mt-1">
              Choose how your query should be processed by the AI
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            aria-label="Close"
          >
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[calc(90vh-180px)]">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {paths.map((path) => {
              const IconComponent = path.icon;
              const isSelected = selectedPath === path.id;

              return (
                <div
                  key={path.id}
                  onClick={() => handlePathSelect(path.id)}
                  className={`relative bg-white rounded-xl border-2 p-5 cursor-pointer transition-all duration-200 ${
                    isSelected
                      ? 'border-primary shadow-lg scale-[1.02]'
                      : 'border-gray-200 hover:border-gray-300 hover:shadow-md'
                  }`}
                >
                  {/* Recommended badge */}
                  {path.recommended && (
                    <div className="absolute -top-2 -right-2 bg-primary text-white text-xs font-semibold px-3 py-1 rounded-full shadow-md">
                      Recommended
                    </div>
                  )}

                  {/* Selected indicator */}
                  {isSelected && (
                    <div className="absolute top-4 right-4 w-6 h-6 bg-primary rounded-full flex items-center justify-center">
                      <svg
                        className="w-4 h-4 text-white"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={3}
                          d="M5 13l4 4L19 7"
                        />
                      </svg>
                    </div>
                  )}

                  {/* Icon */}
                  <div
                    className={`w-14 h-14 rounded-xl bg-gradient-to-br ${path.color} flex items-center justify-center mb-4`}
                  >
                    <IconComponent className="w-7 h-7 text-white" />
                  </div>

                  {/* Title */}
                  <h3 className="font-bold text-lg text-gray-900 mb-1">
                    {path.name}
                  </h3>
                  <p className="text-sm text-gray-500 mb-3">{path.subtitle}</p>

                  {/* Description */}
                  <p className="text-sm text-gray-600 mb-4 leading-relaxed">
                    {path.description}
                  </p>

                  {/* Performance badge */}
                  <div className="inline-flex items-center gap-1 px-3 py-1 bg-gray-100 rounded-full text-xs font-medium text-gray-700">
                    <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                    {path.performance}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-6 border-t border-gray-200 bg-gray-50">
          <p className="text-xs text-gray-500">
            You can change this selection anytime before sending a message
          </p>
          <Button onClick={onClose} variant="secondary" className="w-auto">
            Close
          </Button>
        </div>
      </div>
    </div>
  );
}

// Export memoized version to prevent unnecessary re-renders
export const PathSelector = memo(PathSelectorComponent);

PathSelector.propTypes = {
  isOpen: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  selectedPath: PropTypes.string.isRequired,
  onSelectPath: PropTypes.func.isRequired,
};
