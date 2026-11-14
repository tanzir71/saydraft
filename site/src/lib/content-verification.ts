export const MAX_VERIFIED_AGE_DAYS = 120;

/** UTC calendar dates keep the quarterly check independent of local time zones. */
export function freshVerification(value: string, today = new Date()): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const verified = new Date(`${value}T00:00:00.000Z`);
  if (!Number.isFinite(verified.getTime()) || verified.toISOString().slice(0, 10) !== value) return false;
  const current = Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate());
  const age = current - verified.getTime();
  return age >= 0 && age <= MAX_VERIFIED_AGE_DAYS * 86_400_000;
}
