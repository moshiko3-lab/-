import { expect, test } from "vitest";
import { fmtDur, fromPanama, panamaParts, timeLeft, when, whenFull } from "../lib/time";

const MIN = 60000;

test("time left and overdue", () => {
  const now = Date.UTC(2026, 9, 19, 22, 30);
  expect(timeLeft(now + 75 * MIN, now)).toBe("1h 15m left");
  expect(timeLeft(now + 20 * MIN, now)).toBe("20m left");
  expect(timeLeft(now, now)).toBe("0m left");
  expect(timeLeft(now - 20 * MIN, now)).toBe("Overdue 20m");
  expect(timeLeft(now - 80 * MIN, now)).toBe("Overdue 1h 20m");
  expect(timeLeft(now + (2 * 1440 + 180) * MIN, now)).toBe("2d 3h left");
  expect(fmtDur(-90 * MIN)).toBe("1h 30m");
});

test("times show in Panama, whatever the device's time zone", () => {
  const t = Date.UTC(2026, 9, 19, 22, 30); // 17:30 in Panama (UTC-5)
  expect(when(t)).toBe("19 Oct, 17:30");
  expect(whenFull(t)).toBe("19 Oct 2026, 17:30");
  expect(when(null)).toBe("—");
});

test("calendar parts round-trip through Panama time, across midnight and months", () => {
  const late = Date.UTC(2026, 10, 1, 3, 48); // 1 Nov 03:48 UTC = 31 Oct 22:48 in Panama
  expect(panamaParts(late)).toEqual({ y: 2026, m: 9, d: 31, h: 22, mi: 48 });
  expect(fromPanama(panamaParts(late))).toBe(late);
  expect(fromPanama({ y: 2026, m: 9, d: 19, h: 17, mi: 30 })).toBe(Date.UTC(2026, 9, 19, 22, 30));
});
