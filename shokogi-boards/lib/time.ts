// Every displayed time and every "today" boundary uses the club's time zone.
export const TZ = "America/Panama";

type When = string | number | Date | null | undefined;

export const longDate = (d: Date) =>
  d.toLocaleDateString("en-GB", { timeZone: TZ, weekday: "long", day: "numeric", month: "long", year: "numeric" });

// Lists: "19 Oct, 17:30"
export const when = (t: When) =>
  t ? new Date(t).toLocaleString("en-GB", { timeZone: TZ, day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "—";

// Date fields: "19 Oct 2026, 17:30"
export const whenFull = (t: When) =>
  t ? new Date(t).toLocaleString("en-GB", { timeZone: TZ, day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "Not set";

// "2d 3h", "1h 15m", "20m"
export function fmtDur(ms: number) {
  const a = Math.round(Math.abs(ms) / 60000), d = Math.floor(a / 1440), h = Math.floor((a % 1440) / 60), m = a % 60;
  return d ? `${d}d ${h}h` : h ? `${h}h ${m}m` : `${m}m`;
}

// "1h 15m left" / "Overdue 20m"
export const timeLeft = (due: number, now: number) => (due >= now ? `${fmtDur(due - now)} left` : `Overdue ${fmtDur(now - due)}`);

export const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;

// Panama wall-clock parts for the calendar, whatever time zone the device is set to.
// ponytail: Panama is UTC-5 all year (no daylight saving since 1908); a zone with DST would need Intl parts here.
const OFFSET = 5 * 36e5;
export type Parts = { y: number; m: number; d: number; h: number; mi: number };
export function panamaParts(ms: number): Parts {
  const t = new Date(ms - OFFSET);
  return { y: t.getUTCFullYear(), m: t.getUTCMonth(), d: t.getUTCDate(), h: t.getUTCHours(), mi: t.getUTCMinutes() };
}
export const fromPanama = ({ y, m, d, h, mi }: Parts) => Date.UTC(y, m, d, h, mi) + OFFSET;
