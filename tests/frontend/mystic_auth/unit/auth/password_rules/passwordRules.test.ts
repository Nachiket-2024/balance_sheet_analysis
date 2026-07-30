import { describe, it, expect } from 'vitest';

import { checkPasswordRules, evaluatePasswordStrength, validatePassword } from '@/auth/password_rules/passwordRules';

describe('checkPasswordRules', () => {
  it('flags every rule as failing for an empty password', () => {
    expect(checkPasswordRules('')).toEqual({
      lengthRule: false,
      upperRule: false,
      lowerRule: false,
      numberRule: false,
    });
  });

  it('flags every rule as passing for a password meeting all four rules', () => {
    expect(checkPasswordRules('Password1')).toEqual({
      lengthRule: true,
      upperRule: true,
      lowerRule: true,
      numberRule: true,
    });
  });

  it('evaluates length independently of the other rules', () => {
    expect(checkPasswordRules('Ab1').lengthRule).toBe(false);
    expect(checkPasswordRules('Ab123456').lengthRule).toBe(true);
  });

  it('does not require a special character (mirrors backend validate_password_strength)', () => {
    expect(checkPasswordRules('Password1')).toEqual({
      lengthRule: true,
      upperRule: true,
      lowerRule: true,
      numberRule: true,
    });
  });
});

describe('evaluatePasswordStrength', () => {
  it('returns an empty string for an empty password', () => {
    expect(evaluatePasswordStrength('')).toBe('');
  });

  it('returns Weak when 2 or fewer rules pass', () => {
    expect(evaluatePasswordStrength('abc')).toBe('Weak'); // lowerRule only = 1
    expect(evaluatePasswordStrength('abcdefgh')).toBe('Weak'); // length + lower = 2
  });

  it('returns Medium when exactly 3 rules pass', () => {
    expect(evaluatePasswordStrength('abcdefgH')).toBe('Medium'); // length + lower + upper = 3
  });

  it('returns Strong when all 4 rules pass', () => {
    expect(evaluatePasswordStrength('Password1')).toBe('Strong');
  });
});

describe('validatePassword', () => {
  it('returns null when the password satisfies every rule', () => {
    expect(validatePassword('Password1')).toBeNull();
  });

  it('returns the length error first when the password is too short', () => {
    expect(validatePassword('Ab1')).toBe('Password must be at least 8 characters long');
  });

  it('returns the uppercase error when length is fine but uppercase is missing', () => {
    expect(validatePassword('password1')).toBe('Password must contain at least one uppercase letter');
  });

  it('returns the lowercase error when uppercase/length are fine but lowercase is missing', () => {
    expect(validatePassword('PASSWORD1')).toBe('Password must contain at least one lowercase letter');
  });

  it('returns the number error when only the digit rule is missing', () => {
    expect(validatePassword('Password')).toBe('Password must contain at least one number');
  });
});
