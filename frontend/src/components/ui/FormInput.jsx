/**
 * FormInput Component
 * Reusable input field with icon and validation
 */
export function FormInput({
  type,
  placeholder,
  value,
  onChange,
  icon,
  error,
  required = false,
  maxLength = 255,
  autoComplete,
}) {
  return (
    <div className="w-full">
      <div className="relative">
        <input
          type={type}
          placeholder={placeholder}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          required={required}
          maxLength={maxLength}
          autoComplete={autoComplete}
          aria-label={placeholder}
          aria-invalid={!!error}
          aria-describedby={error ? `${placeholder}-error` : undefined}
          className={`w-full px-4 py-3 pr-12 bg-white border-2 rounded-xl outline-none transition-all focus:ring-2 focus:ring-primary focus:ring-opacity-50 ${
            error ? 'border-red-400' : 'border-gray-200 focus:border-primary'
          }`}
        />
        {icon && (
          <div
            className="absolute right-4 top-1/2 -translate-y-1/2 text-primary"
            aria-hidden="true"
          >
            {icon}
          </div>
        )}
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
    </div>
  );
}
