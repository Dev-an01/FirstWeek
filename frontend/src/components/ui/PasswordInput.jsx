import { useState } from 'react';
import { Eye, EyeOff, Lock } from 'lucide-react';
import { validatePassword } from '../../utils/validators';

/**
 * PasswordInput Component
 * Password field with show/hide toggle and strength indicator
 */
export function PasswordInput({
  placeholder,
  value,
  onChange,
  error,
  showStrength = false,
  required = false,
  autoComplete = 'current-password',
}) {
  const [showPassword, setShowPassword] = useState(false);
  const validation = validatePassword(value);

  return (
    <div className="w-full">
      <div className="relative">
        <input
          type={showPassword ? 'text' : 'password'}
          placeholder={placeholder}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          required={required}
          maxLength={128}
          autoComplete={autoComplete}
          aria-label={placeholder}
          aria-invalid={!!error}
          aria-describedby={
            error
              ? `${placeholder}-error`
              : showStrength
                ? `${placeholder}-strength`
                : undefined
          }
          className={`w-full px-4 py-3 pr-24 bg-white border-2 rounded-xl outline-none transition-all focus:ring-2 focus:ring-primary focus:ring-opacity-50 ${
            error ? 'border-red-400' : 'border-gray-200 focus:border-primary'
          }`}
        />
        <div className="absolute right-4 top-1/2 -translate-y-1/2 flex gap-2">
          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            className="text-primary hover:text-primary-dark transition-colors focus:outline-none focus:ring-2 focus:ring-primary rounded"
            aria-label={showPassword ? 'Hide password' : 'Show password'}
            tabIndex={0}
          >
            {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
          </button>
          <Lock size={20} className="text-primary" aria-hidden="true" />
        </div>
      </div>
      {error && (
        <p
          id={`${placeholder}-error`}
          className="text-red-500 text-sm mt-1 ml-2"
          role="alert"
        >
          {error}
        </p>
      )}
      {showStrength && value && !error && (
        <p
          id={`${placeholder}-strength`}
          className={`text-sm mt-1 ml-2 ${validation.valid ? 'text-green-600' : 'text-gray-600'}`}
          role="status"
          aria-live="polite"
        >
          {validation.message}
        </p>
      )}
    </div>
  );
}
