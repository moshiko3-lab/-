#!/usr/bin/env python3
"""The one calculation the whole thing rests on: which hours are free.

Every other bug is annoying. This one puts two women in the same chair at
the same time, so it is tested against the built page rather than against
the source, and with the clock pinned so the answers do not change at 6pm.
"""
import datetime
import sys
from playwright.sync_api import sync_playwright
from harness import browser, phone, open_page, ok, done


def book():
    """A studio open Monday to Saturday, with one appointment on the books."""
    return {
        "v": 1,
        "settings": {
            "name": "Test Studio", "phone": "61234567", "hours": {
                "0": [], "1": [{"from": "09:00", "to": "17:00"}],
                "2": [{"from": "09:00", "to": "17:00"}],
                "3": [{"from": "09:00", "to": "17:00"}],
                "4": [{"from": "09:00", "to": "17:00"}],
                "5": [{"from": "09:00", "to": "17:00"}],
                "6": [{"from": "09:00", "to": "13:00"}]},
            "step": 30, "buffer": 10, "leadHours": 2, "horizon": 30,
            "cancelHours": 24, "autoConfirm": True, "noteHe": "", "noteEn": ""
        },
        "services": [
            {"id": "s-a", "he": "קצר", "en": "Short", "minutes": 30, "price": 25,
             "form": False, "active": True},
            {"id": "s-b", "he": "ארוך", "en": "Long", "minutes": 90, "price": 80,
             "form": True, "active": True}],
        "clients": [], "appointments": [], "blocks": [], "forms": []
    }


def slots(pg, date, minutes):
    return pg.evaluate(
        "([d,m]) => freeSlots(db, d, m).map(min2hm)", [date, minutes])


def main():
    with sync_playwright() as p:
        b = browser(p)

        # a Monday well in the future, so "today" and lead time never matter
        d = datetime.date.today() + datetime.timedelta(days=14)
        while d.weekday() != 0:          # 0 = Monday in python
            d += datetime.timedelta(days=1)
        monday = d.isoformat()
        sunday = (d - datetime.timedelta(days=1)).isoformat()

        pg = open_page(phone(b, seed=book()), "book.html")
        free = slots(pg, monday, 30)
        ok(free[0] == "09:00" and free[-1] == "16:30",
           "an open day runs from opening to the last slot that still fits")
        ok(len(free) == 16, "30-minute steps across eight hours give sixteen slots")

        long = slots(pg, monday, 90)
        ok(long[-1] == "15:30", "a 90-minute treatment is not offered at 16:30")

        ok(slots(pg, sunday, 30) == [], "a closed day offers nothing")

        # one appointment at 11:00 for 30 minutes, with 10 minutes of buffer
        seeded = book()
        seeded["appointments"].append({
            "id": "a1", "clientName": "Ana", "phone": "50761111111",
            "serviceId": "s-a", "date": monday, "time": "11:00",
            "minutes": 30, "price": 25, "status": "confirmed"})
        pg = open_page(phone(b, seed=seeded), "book.html")
        free = slots(pg, monday, 30)
        ok("11:00" not in free, "the booked hour is gone")
        ok("10:30" not in free,
           "and so is the half hour before it, which would have run into it")
        ok("12:00" in free, "the next clear slot is still offered")

        # the buffer is what keeps the day from sliding: 11:30 ends at 11:40
        seeded2 = book()
        seeded2["appointments"].append({
            "id": "a2", "clientName": "Ana", "phone": "50761111111",
            "serviceId": "s-a", "date": monday, "time": "11:30",
            "minutes": 30, "price": 25, "status": "confirmed"})
        pg = open_page(phone(b, seed=seeded2), "book.html")
        free = slots(pg, monday, 30)
        ok("12:00" not in free,
           "ten minutes of tidying up after a 12:00 finish blocks the 12:00 slot")
        ok("12:30" in free, "and the one after it is free again")

        # a cancelled appointment gives the hour back
        seeded3 = book()
        seeded3["appointments"].append({
            "id": "a3", "clientName": "Ana", "phone": "50761111111",
            "serviceId": "s-a", "date": monday, "time": "11:00",
            "minutes": 30, "price": 25, "status": "cancelled"})
        pg = open_page(phone(b, seed=seeded3), "book.html")
        ok("11:00" in slots(pg, monday, 30), "a cancelled appointment frees its hour")

        # a block is time off, and it disappears from the client's view too
        seeded4 = book()
        seeded4["blocks"].append({"id": "b1", "date": monday, "from": "09:00",
                                  "to": "12:00", "reason": "dentist"})
        pg = open_page(phone(b, seed=seeded4), "book.html")
        free = slots(pg, monday, 30)
        ok(free[0] == "12:00", "a blocked morning is not offered")

        # a treatment that does not fit the short Saturday window
        saturday = (d + datetime.timedelta(days=5)).isoformat()
        pg = open_page(phone(b, seed=book()), "book.html")
        ok(slots(pg, saturday, 90)[-1] == "11:30",
           "Saturday closes at one, so the last long slot starts at 11:30")

        done("test_slots", pg)
        b.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
