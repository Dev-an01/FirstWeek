/**
 * VoiceSampleUploader Component
 *
 * Upload voice samples (reference + consent), preview audio, validate via STT,
 * and generate per-executive voice cloning keys via Chirp3 API.
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import PropTypes from 'prop-types';
import {
  Upload,
  Play,
  Pause,
  CheckCircle,
  XCircle,
  AlertCircle,
  RefreshCw,
  Trash2,
  Volume2,
  Mic,
  Square,
} from 'lucide-react';
import { Button } from '../ui/Button';
import { useOnboardingStore } from '../../store/onboardingStore';
import { useUIStore } from '../../store/uiStore';

const ACCEPTED_AUDIO = '.wav,.mp3,.webm,.m4a';

const CONSENT_SCRIPTS = {
  en: 'I am the owner of this voice and I consent to Google using this voice to create a synthetic voice model.',
  ja: '私はこの音声の所有者であり、Googleがこの音声を使用して音声合成 モデルを作成することを承認します。',
};

const LANGUAGE_LABELS = {
  en: 'English',
  ja: 'Japanese',
};

const LANGUAGE_CODES = {
  en: 'en-US',
  ja: 'ja-JP',
};

function formatDuration(seconds) {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function AudioFileInput({ label, file, onFileChange, audioUrl, disabled }) {
  const inputRef = useRef(null);
  const audioRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const timerRef = useRef(null);

  const [isPlaying, setIsPlaying] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [recordingDuration, setRecordingDuration] = useState(0);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (mediaRecorderRef.current?.state === 'recording') {
        mediaRecorderRef.current.stream.getTracks().forEach((t) => t.stop());
        mediaRecorderRef.current.stop();
      }
    };
  }, []);

  const handlePlay = useCallback(() => {
    if (!audioRef.current) return;
    if (isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
    } else {
      audioRef.current.play();
      setIsPlaying(true);
    }
  }, [isPlaying]);

  const handleEnded = useCallback(() => setIsPlaying(false), []);

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : undefined,
      });
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      mediaRecorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: mediaRecorder.mimeType });
        const ext = mediaRecorder.mimeType.includes('webm') ? 'webm' : 'wav';
        const recorded = new File([blob], `recording_${Date.now()}.${ext}`, {
          type: mediaRecorder.mimeType,
        });
        onFileChange(recorded);
        stream.getTracks().forEach((t) => t.stop());
      };

      mediaRecorder.start();
      setIsRecording(true);
      setRecordingDuration(0);
      timerRef.current = setInterval(() => setRecordingDuration((d) => d + 1), 1000);
    } catch {
      // Microphone access denied or unavailable
    }
  }, [onFileChange]);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current?.state === 'recording') {
      mediaRecorderRef.current.stop();
    }
    setIsRecording(false);
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  return (
    <div className="flex items-center gap-3">
      <span className="text-sm text-gray-600 w-32 flex-shrink-0">{label}:</span>
      <div className="flex-1 flex items-center gap-2">
        {isRecording ? (
          <>
            <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse flex-shrink-0" />
            <span className="text-sm text-red-600 tabular-nums">
              Recording {formatDuration(recordingDuration)}
            </span>
            <button
              onClick={stopRecording}
              className="p-1.5 rounded-lg bg-red-50 hover:bg-red-100 text-red-600 transition-colors"
              title="Stop recording"
            >
              <Square className="w-4 h-4" />
            </button>
          </>
        ) : file ? (
          <>
            <span className="text-sm text-gray-700 truncate max-w-[180px]">{file.name}</span>
            <button
              onClick={handlePlay}
              disabled={!audioUrl}
              className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500 hover:text-primary transition-colors disabled:opacity-50"
              title={isPlaying ? 'Pause' : 'Play'}
            >
              {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
            </button>
            <button
              onClick={() => onFileChange(null)}
              disabled={disabled}
              className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-red-500 transition-colors disabled:opacity-50"
              title="Remove"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
            {audioUrl && (
              <audio ref={audioRef} src={audioUrl} onEnded={handleEnded} className="hidden" />
            )}
          </>
        ) : (
          <>
            <button
              onClick={() => !disabled && inputRef.current?.click()}
              disabled={disabled}
              className={`
                flex-1 border-2 border-dashed rounded-lg p-3 text-center transition-all
                ${disabled ? 'opacity-50 cursor-not-allowed border-gray-200' : 'cursor-pointer hover:border-primary hover:bg-gray-50 border-gray-300'}
              `}
            >
              <div className="flex items-center justify-center gap-2 text-sm text-gray-500">
                <Upload className="w-4 h-4" />
                <span>Upload file</span>
              </div>
            </button>
            <span className="text-xs text-gray-400">or</span>
            <button
              onClick={startRecording}
              disabled={disabled}
              className={`
                flex items-center gap-1.5 px-3 py-2.5 rounded-lg border-2 transition-all text-sm
                ${disabled ? 'opacity-50 cursor-not-allowed border-gray-200 text-gray-400' : 'cursor-pointer hover:border-red-300 hover:bg-red-50 border-gray-300 text-gray-600 hover:text-red-600'}
              `}
              title="Record from microphone"
            >
              <Mic className="w-4 h-4" />
              <span>Record</span>
            </button>
          </>
        )}
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_AUDIO}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) onFileChange(f);
            if (inputRef.current) inputRef.current.value = '';
          }}
          className="hidden"
          disabled={disabled}
        />
      </div>
    </div>
  );
}

export function VoiceSampleUploader({ companyId, executiveId, language, hasExistingKey, onKeyGenerated }) {
  const validateVoiceSamples = useOnboardingStore((s) => s.validateVoiceSamples);
  const generateVoiceKey = useOnboardingStore((s) => s.generateVoiceKey);
  const deleteVoiceKey = useOnboardingStore((s) => s.deleteVoiceKey);
  const showSuccessToast = useUIStore((s) => s.showSuccessToast);
  const showErrorToast = useUIStore((s) => s.showErrorToast);

  const [referenceFile, setReferenceFile] = useState(null);
  const [consentFile, setConsentFile] = useState(null);
  const [referenceUrl, setReferenceUrl] = useState(null);
  const [consentUrl, setConsentUrl] = useState(null);

  const [validating, setValidating] = useState(false);
  const [validationResult, setValidationResult] = useState(null);

  const [generating, setGenerating] = useState(false);
  const [generationResult, setGenerationResult] = useState(null);

  const languageCode = LANGUAGE_CODES[language];
  const languageLabel = LANGUAGE_LABELS[language];
  const consentScript = CONSENT_SCRIPTS[language];

  const handleReferenceChange = useCallback((file) => {
    if (referenceUrl) URL.revokeObjectURL(referenceUrl);
    setReferenceFile(file);
    setReferenceUrl(file ? URL.createObjectURL(file) : null);
    setValidationResult(null);
    setGenerationResult(null);
  }, [referenceUrl]);

  const handleConsentChange = useCallback((file) => {
    if (consentUrl) URL.revokeObjectURL(consentUrl);
    setConsentFile(file);
    setConsentUrl(file ? URL.createObjectURL(file) : null);
    setValidationResult(null);
    setGenerationResult(null);
  }, [consentUrl]);

  const handleValidate = useCallback(async () => {
    if (!referenceFile || !consentFile) return;
    setValidating(true);
    setValidationResult(null);
    try {
      const result = await validateVoiceSamples(companyId, executiveId, referenceFile, consentFile, language);
      setValidationResult(result);
    } catch (error) {
      showErrorToast(error.message || 'Validation failed');
    } finally {
      setValidating(false);
    }
  }, [referenceFile, consentFile, companyId, executiveId, language, validateVoiceSamples, showErrorToast]);

  const handleGenerate = useCallback(async () => {
    if (!referenceFile || !consentFile) return;
    setGenerating(true);
    setGenerationResult(null);
    try {
      const result = await generateVoiceKey(companyId, executiveId, referenceFile, consentFile, language);
      setGenerationResult(result);
      showSuccessToast(`${languageLabel} voice key generated (${result.key_length?.toLocaleString()} chars)`);
      onKeyGenerated?.();
    } catch (error) {
      showErrorToast(error.message || 'Key generation failed');
    } finally {
      setGenerating(false);
    }
  }, [referenceFile, consentFile, companyId, executiveId, language, languageLabel, generateVoiceKey, showSuccessToast, showErrorToast, onKeyGenerated]);

  const handleDelete = useCallback(async () => {
    try {
      await deleteVoiceKey(companyId, executiveId, language);
      showSuccessToast(`${languageLabel} voice key deleted`);
      setGenerationResult(null);
      onKeyGenerated?.();
    } catch (error) {
      showErrorToast(error.message || 'Failed to delete key');
    }
  }, [companyId, executiveId, language, languageLabel, deleteVoiceKey, showSuccessToast, showErrorToast, onKeyGenerated]);

  const canValidate = referenceFile && consentFile && !validating;
  const canGenerate = validationResult?.valid && !generating;

  return (
    <div className="border border-gray-200 rounded-xl p-4 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Volume2 className="w-4 h-4 text-primary" />
          <h3 className="font-medium text-gray-900">{languageLabel} Voice Key</h3>
        </div>
        {hasExistingKey ? (
          <div className="flex items-center gap-2">
            <span className="text-xs bg-green-50 text-green-700 px-2 py-0.5 rounded-full flex items-center gap-1">
              <CheckCircle className="w-3 h-3" />
              Active
            </span>
            <button
              onClick={handleDelete}
              className="text-xs text-gray-400 hover:text-red-500 transition-colors"
              title="Delete key"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
        ) : (
          <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">
            No Key
          </span>
        )}
      </div>

      {/* Audio File Inputs */}
      <AudioFileInput
        label="Reference Audio"
        file={referenceFile}
        onFileChange={handleReferenceChange}
        audioUrl={referenceUrl}
        disabled={validating || generating}
      />
      <AudioFileInput
        label="Consent Audio"
        file={consentFile}
        onFileChange={handleConsentChange}
        audioUrl={consentUrl}
        disabled={validating || generating}
      />

      {/* Consent Script */}
      <div className="bg-gray-50 rounded-lg p-3">
        <p className="text-xs text-gray-500 mb-1">Consent script (read aloud):</p>
        <p className="text-sm text-gray-700 italic">&ldquo;{consentScript}&rdquo;</p>
      </div>

      {/* Validate Button */}
      <Button
        onClick={handleValidate}
        disabled={!canValidate}
        variant="outline"
        className="w-full"
      >
        {validating ? (
          <>
            <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
            Validating...
          </>
        ) : (
          'Validate Samples'
        )}
      </Button>

      {/* Validation Results */}
      {validationResult && (
        <div className="space-y-2 text-sm">
          <div className={`flex items-start gap-2 p-2 rounded-lg ${validationResult.reference.valid ? 'bg-green-50' : 'bg-red-50'}`}>
            {validationResult.reference.valid ? (
              <CheckCircle className="w-4 h-4 text-green-500 mt-0.5 flex-shrink-0" />
            ) : (
              <XCircle className="w-4 h-4 text-red-500 mt-0.5 flex-shrink-0" />
            )}
            <div>
              <p className={validationResult.reference.valid ? 'text-green-700' : 'text-red-700'}>
                Reference: {validationResult.reference.message}
              </p>
              {validationResult.reference.transcript && (
                <p className="text-gray-500 text-xs mt-1 truncate max-w-md">
                  &ldquo;{validationResult.reference.transcript}&rdquo;
                </p>
              )}
            </div>
          </div>

          <div className={`flex items-start gap-2 p-2 rounded-lg ${validationResult.consent.valid ? 'bg-green-50' : 'bg-red-50'}`}>
            {validationResult.consent.valid ? (
              <CheckCircle className="w-4 h-4 text-green-500 mt-0.5 flex-shrink-0" />
            ) : (
              <XCircle className="w-4 h-4 text-red-500 mt-0.5 flex-shrink-0" />
            )}
            <div>
              <p className={validationResult.consent.valid ? 'text-green-700' : 'text-red-700'}>
                Consent: {validationResult.consent.message}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Generate Key Button */}
      {validationResult?.valid && (
        <Button
          onClick={handleGenerate}
          disabled={!canGenerate}
          className="w-full"
        >
          {generating ? (
            <>
              <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
              Generating Key...
            </>
          ) : hasExistingKey ? (
            'Regenerate Voice Key'
          ) : (
            'Generate Voice Key'
          )}
        </Button>
      )}

      {/* Generation Result */}
      {generationResult?.success && (
        <div className="flex items-center gap-2 p-2 bg-green-50 rounded-lg text-sm text-green-700">
          <CheckCircle className="w-4 h-4 flex-shrink-0" />
          <span>Key generated ({generationResult.key_length?.toLocaleString()} chars)</span>
        </div>
      )}
    </div>
  );
}

VoiceSampleUploader.propTypes = {
  companyId: PropTypes.string.isRequired,
  executiveId: PropTypes.string.isRequired,
  language: PropTypes.oneOf(['en', 'ja']).isRequired,
  hasExistingKey: PropTypes.bool,
  onKeyGenerated: PropTypes.func,
};

export default VoiceSampleUploader;
