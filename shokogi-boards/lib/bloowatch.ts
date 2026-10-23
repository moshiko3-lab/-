// Bloowatch bookings (SPEC 7.12). There is no Bloowatch API access yet, so this is only the seam: a booking in a
// neutral shape that becomes (or updates) a rental. When Bloowatch's docs arrive, map their payload in
// parseBooking and nothing else changes. No Bloowatch endpoints are assumed.
export type Booking = { bookingId: string; name: string; phone: string; startsAt: string; dueAt: string };

export function parseBooking(body: unknown): Booking {
  const b = (body ?? {}) as Record<string, unknown>;
  const text = (k: string) => (typeof b[k] === "string" ? (b[k] as string).trim() : "");
  const booking = { bookingId: text("booking_id"), name: text("name"), phone: text("phone"), startsAt: text("starts_at"), dueAt: text("due_at") };
  if (!booking.bookingId || !booking.name) throw new Error("booking_id and name are required.");
  if (Number.isNaN(Date.parse(booking.startsAt)) || Number.isNaN(Date.parse(booking.dueAt))) throw new Error("starts_at and due_at must be dates (ISO 8601).");
  if (Date.parse(booking.dueAt) <= Date.parse(booking.startsAt)) throw new Error("due_at must be after starts_at.");
  return booking;
}
