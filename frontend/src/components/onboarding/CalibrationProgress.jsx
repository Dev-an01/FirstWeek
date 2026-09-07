/**
 * CalibrationProgress Component
 *
 * Displays calibration/onboarding job progress.
 */

import { useMemo } from 'react';
import PropTypes from 'prop-types';
import { CheckCircle, XCircle, Loader2, Clock } from 'lucide-react';

const STAGES = [
  { key: 'pending', label: 'Queued' },
  { key: 'parsing', label: 'Parsing Documents' },
  { key: 'extracting', label: 'Extracting Profile' },
  { key: 'assembling', label: 'Assembling Profile' },
  { key: 'validating', label: 'Validating' },
  { key: 'deploying', label: 'Deploying' },
  { key: 'embedding', label: 'Generating Embeddings' },
  { key: 'completed', label: 'Completed' },
];

const STAGE_INDEX = STAGES.reduce((acc, stage, i) => {
  acc[stage.key] = i;
  return acc;
}, {});

export function CalibrationProgress({ job, onCancel }) {
  const currentStageIndex = useMemo(() => {
    if (!job?.status) return 0;
    return STAGE_INDEX[job.status.toLowerCase()] ?? 0;
  }, [job?.status]);

  const isCompleted = job?.status === 'completed';
  const isFailed = job?.status === 'failed';
  const isRunning = !isCompleted && !isFailed;

  // Calculate progress percentage
  const progress = useMemo(() => {
    if (isCompleted) return 100;
    if (isFailed) return currentStageIndex / (STAGES.length - 1) * 100;
    if (job?.progress !== undefined) return Math.round(job.progress * 100);
    return (currentStageIndex / (STAGES.length - 1)) * 100;
  }, [isCompleted, isFailed, currentStageIndex, job?.progress]);

  if (!job) return null;

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          {isCompleted && <CheckCircle className="w-5 h-5 text-green-500" />}
          {isFailed && <XCircle className="w-5 h-5 text-red-500" />}
          {isRunning && <Loader2 className="w-5 h-5 text-primary animate-spin" />}

          <span className="font-medium text-gray-900">
            {isCompleted && 'Calibration Complete'}
            {isFailed && 'Calibration Failed'}
            {isRunning && 'Calibrating...'}
          </span>
        </div>

        {isRunning && onCancel && (
          <button
            onClick={onCancel}
            className="text-sm text-gray-500 hover:text-gray-700"
          >
            Cancel
          </button>
        )}
      </div>

      {/* Progress Bar */}
      <div className="mb-4">
        <div className="flex items-center justify-between text-sm mb-1">
          <span className="text-gray-600">
            {STAGES[currentStageIndex]?.label || 'Processing'}
          </span>
          <span className="text-gray-500">{Math.round(progress)}%</span>
        </div>
        <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${
              isFailed ? 'bg-red-500' : isCompleted ? 'bg-green-500' : 'bg-primary'
            }`}
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Stage Steps (Compact) */}
      <div className="flex items-center gap-1 overflow-x-auto pb-2">
        {STAGES.slice(0, -1).map((stage, index) => {
          const isActive = index === currentStageIndex;
          const isDone = index < currentStageIndex;
          const isCurrent = isActive && isRunning;

          return (
            <div
              key={stage.key}
              className={`
                flex items-center gap-1 px-2 py-1 rounded-full text-xs whitespace-nowrap
                ${isDone ? 'bg-green-100 text-green-700' : ''}
                ${isCurrent ? 'bg-primary-light text-primary' : ''}
                ${!isDone && !isCurrent ? 'bg-gray-100 text-gray-400' : ''}
              `}
            >
              {isDone && <CheckCircle className="w-3 h-3" />}
              {isCurrent && <Loader2 className="w-3 h-3 animate-spin" />}
              {!isDone && !isCurrent && <Clock className="w-3 h-3" />}
              <span className="hidden sm:inline">{stage.label}</span>
            </div>
          );
        })}
      </div>

      {/* Error Message */}
      {isFailed && job.error_message && (
        <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-sm text-red-600">{job.error_message}</p>
        </div>
      )}

      {/* Job ID (for debugging) */}
      <div className="mt-3 pt-3 border-t border-gray-100">
        <p className="text-xs text-gray-400">
          Job ID: {job.id || job.job_id}
        </p>
      </div>
    </div>
  );
}

CalibrationProgress.propTypes = {
  job: PropTypes.shape({
    id: PropTypes.string,
    job_id: PropTypes.string,
    status: PropTypes.string,
    progress: PropTypes.number,
    error_message: PropTypes.string,
  }),
  onCancel: PropTypes.func,
};

export default CalibrationProgress;
