// Content-safety guard: detects contact data (email addresses or North-American
// phone numbers) in string values. Validators reject any entry whose string fields
// contain contact data, and render-time test assertions reuse this to confirm no
// investigator/contact/official name, email, or phone number is ever exposed
// (Req 2.13, 7.3, 17.*; product.md non-negotiable rules).

// Email: non-whitespace, @, non-whitespace, dot, non-whitespace (per design).
const EMAIL_PATTERN = /\S+@\S+\.\S+/;

// North-American (NANP) phone: optional "+1"/"1" country code, then a 10-digit
// number in 3-3-4 groups with optional separators (space, dot, hyphen) and an
// optional parenthesized area code. The explicit 3-3-4 grouping keeps the pattern
// from matching arbitrary digit runs such as years (2024) or ZIP codes (02139).
const PHONE_PATTERN =
  /(?:\+?1[\s.-]?)?(?:\(\d{3}\)|\d{3})[\s.-]?\d{3}[\s.-]?\d{4}/;

/**
 * Returns true when `value` contains an email address or a North-American phone
 * number, false otherwise. Non-string input is treated defensively as safe.
 */
export function containsContactData(value: string): boolean {
  if (typeof value !== "string") {
    return false;
  }
  return EMAIL_PATTERN.test(value) || PHONE_PATTERN.test(value);
}
