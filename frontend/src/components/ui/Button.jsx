/**
 * Button Component
 * Reusable button with variants and loading states
 */
export function Button({
  children,
  onClick,
  type = 'button',
  variant = 'primary',
  disabled = false,
  className = '',
  fullWidth = true,
}) {
  const widthClass = fullWidth ? 'w-full' : 'w-auto';
  const baseStyles =
    `${widthClass} py-3 px-6 rounded-full font-medium transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary`;

  const variantStyles = {
    primary: 'bg-primary text-white hover:bg-primary-dark active:scale-98',
    secondary: 'bg-white text-primary border-2 border-primary hover:bg-gray-50',
    outline:
      'bg-transparent text-primary border-2 border-primary hover:bg-primary hover:text-white',
  };

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`${baseStyles} ${variantStyles[variant]} ${className}`}
      aria-disabled={disabled}
    >
      {children}
    </button>
  );
}
