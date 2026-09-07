import { sanitizeInput } from '../sanitizer';

test('sanitizes text', () => {
  expect(sanitizeInput('<b>hi</b>')).toBe('bhi/b');
});
