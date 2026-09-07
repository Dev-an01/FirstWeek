import { memo } from 'react';
import { Volume2, VolumeX } from 'lucide-react';
import { useChatStore } from '../../store/chatStore';

/**
 * TTS Toggle Component
 *
 * Toggle button to enable/disable text-to-speech audio
 *
 * Features:
 * - Visual toggle with speaker icon
 * - Shows enabled/disabled state with color
 * - Persists setting in Zustand store
 * - Stops audio playback if clicked during playback
 */
function TTSToggleComponent({ disabled = false, className = '', onStopAudio }) {
  const { ttsEnabled, toggleTTS, audioPlaying } = useChatStore();

  const handleClick = () => {
    // If audio is currently playing, stop it first
    if (audioPlaying && onStopAudio) {
      onStopAudio();
    }
    // Then toggle TTS setting
    toggleTTS();
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={disabled}
      className={`
        flex items-center gap-2 px-4 py-2 rounded-lg border transition-all duration-200
        ${
          ttsEnabled
            ? 'bg-primary text-white border-primary hover:bg-primary-dark'
            : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
        }
        ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
        ${audioPlaying ? 'animate-pulse' : ''}
        ${className}
      `}
      title={ttsEnabled ? 'Disable voice responses' : 'Enable voice responses'}
      aria-label={
        ttsEnabled ? 'Disable voice responses' : 'Enable voice responses'
      }
    >
      {ttsEnabled ? (
        <Volume2 className="w-4 h-4" />
      ) : (
        <VolumeX className="w-4 h-4" />
      )}
      <span className="text-sm font-medium">
        {ttsEnabled ? 'Voice: ON' : 'Voice: OFF'}
      </span>
      {audioPlaying && <span className="text-xs opacity-75">(Playing...)</span>}
    </button>
  );
}

// Export memoized version to prevent unnecessary re-renders
export const TTSToggle = memo(TTSToggleComponent);
