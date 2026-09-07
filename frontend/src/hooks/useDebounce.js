import { useState, useEffect } from 'react';

/**
 * useDebounce Hook
 *
 * Debounces a value by delaying updates until after a specified delay
 *
 * @param {any} value - The value to debounce
 * @param {number} delay - Delay in milliseconds (default: 300ms)
 * @returns {any} The debounced value
 *
 * Example:
 *   const [searchQuery, setSearchQuery] = useState('');
 *   const debouncedQuery = useDebounce(searchQuery, 300);
 *
 *   debouncedQuery only updates 300ms after user stops typing
 */
export function useDebounce(value, delay = 300) {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    // Set up the timeout to update debounced value after delay
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    // Clean up the timeout if value changes before delay expires
    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
}
