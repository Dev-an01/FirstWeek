import { validateEmail, validatePassword } from '../validators';

test('valid email', () => {
  expect(validateEmail('a@b.com')).toBe(true);
});

test('strong password', () => {
  expect(validatePassword('Password1').valid).toBe(true);
});
