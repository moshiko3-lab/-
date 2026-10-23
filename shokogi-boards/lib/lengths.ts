// Rental lengths are stored in minutes and shown in the biggest unit that reads naturally (SPEC 7.9):
// 1440 -> 1 day, 2880 -> 2 days, 150 -> 2.5 hours, 90 -> 1.5 hours, 45 -> 45 minutes.
export const UNITS: [minutes: number, name: string][] = [[1440, "days"], [60, "hours"], [1, "minutes"]];

export const lengthUnit = (minutes: number) => (minutes % 1440 === 0 ? 1440 : minutes % 30 === 0 ? 60 : 1);
export const toMinutes = (amount: number, unit: number) => Math.round(amount * unit);
