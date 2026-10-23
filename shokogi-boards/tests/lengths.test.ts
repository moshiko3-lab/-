import { expect, test } from "vitest";
import { lengthUnit, toMinutes } from "../lib/lengths";

const show = (m: number) => `${m / lengthUnit(m)} ${lengthUnit(m)}`;

test("rental lengths show in the natural unit", () => {
  expect(show(150)).toBe("2.5 60");
  expect(show(90)).toBe("1.5 60");
  expect(show(240)).toBe("4 60");
  expect(show(1440)).toBe("1 1440");
  expect(show(2880)).toBe("2 1440");
  expect(show(10080)).toBe("7 1440");
  expect(show(45)).toBe("45 1");
  expect(show(50)).toBe("50 1");
});

test("amount and unit back to minutes", () => {
  expect(toMinutes(2.5, 60)).toBe(150);
  expect(toMinutes(1, 1440)).toBe(1440);
  expect(toMinutes(0.25, 60)).toBe(15);
});
