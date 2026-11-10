/**
 * Field rules and their copy, from UX_SPEC S-02 "Fields". The copy is the
 * spec's, word for word. No strength meter (U1 — it nags without helping).
 */

export const MIN_PASSWORD = 8;

// The most common passwords of eight or more characters. A short list on
// purpose: Supabase's own leaked-password check is the real defence, and this
// only catches the ones a person is most likely to try first.
const COMMON = new Set([
  "password", "password1", "password12", "password123", "password!", "passw0rd",
  "12345678", "123456789", "1234567890", "123123123", "11111111", "00000000",
  "87654321", "11223344", "12341234", "qwertyuiop", "qwerty123", "qwerty12",
  "1q2w3e4r", "1qaz2wsx", "zaq12wsx", "abcd1234", "abc12345", "abcdefgh",
  "iloveyou", "iloveyou1", "sunshine", "princess", "football", "baseball",
  "welcome1", "welcome123", "superman", "starwars", "trustno1", "letmein1",
  "whatever", "dragon123", "monkey123", "michael1", "computer", "internet",
  "asdfghjkl", "asdf1234", "admin123", "administrator", "changeme", "default1",
  "doctor123", "medicine", "hospital", "mbbs1234", "nidan123", "student1",
]);

export function normaliseEmail(raw: string): string {
  return raw.trim().toLowerCase();
}

// Deliberately permissive: one @, something either side, a dot in the domain.
// Supabase validates properly; this only catches typos before the round trip.
// Apple private-relay addresses are ordinary addresses (UX_SPEC §6.1.2).
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function emailError(raw: string): string | null {
  return EMAIL.test(normaliseEmail(raw)) ? null : "Enter a valid email address";
}

export function passwordError(password: string): string | null {
  if (password.length < MIN_PASSWORD) return "Use at least 8 characters";
  if (COMMON.has(password.toLowerCase())) {
    return "That password is too common — try something less predictable";
  }
  return null;
}
