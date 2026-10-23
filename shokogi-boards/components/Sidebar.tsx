"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { Profile } from "@/lib/auth";
import { useState } from "react";
import { isOverdue } from "@/lib/data";
import { TZ } from "@/lib/time";
import { useApp } from "./app";
import { Icon, type IconName } from "./icons";
import ExportButton from "./ExportButton";
import SignOut from "./SignOut";

const clock = (t: string) => new Date(t).toLocaleTimeString("en-GB", { timeZone: TZ, hour: "2-digit", minute: "2-digit" });

const NAV: [href: string, label: string, icon: IconName][] = [
  ["/", "Dashboard", "dash"],
  ["/rentals", "Rentals", "clip"],
  ["/customers", "Customers", "users"],
  ["/boards", "Boards", "board"],
  ["/history", "History", "clock"],
  ["/settings", "Settings", "sliders"],
];

export default function Sidebar({ me }: { me: Profile }) {
  const path = usePathname();
  const { fleet, now, syncNow } = useApp();
  const [syncing, setSyncing] = useState(false);
  const late = fleet?.rentals.filter((r) => isOverdue(r, now)).length;
  return (
    <aside>
      <div className="brand">
        <span className="logo">S</span>
        <div><b>Shokogi</b><small>Board rentals</small></div>
      </div>
      <nav>
        {NAV.filter(([href]) => href !== "/settings" || me.role === "owner").map(([href, label, icon]) => (
          <Link key={href} href={href} className={path === href ? "on" : undefined}>
            <Icon name={icon} />{label}
            {href === "/rentals" && <span className="count" title="Overdue">{late || ""}</span>}
          </Link>
        ))}
      </nav>
      <div className="sync">
        <b><Icon name="sheet" />Google Sheets</b>
        <span id="syncStatus" title={fleet?.sheets?.error ?? undefined}>
          {!fleet?.sheet ? "Not connected" : !fleet.sheets ? "Connected" : fleet.sheets.error ? "Sync failed, will retry" : `Synced ${clock(fleet.sheets.at)}`}
        </span>
        {fleet?.sheet && (
          <div className="sync-actions">
            <a className="link" href={fleet.sheet.url} target="_blank" rel="noopener">Open sheet</a>
            <button className="link" disabled={syncing} onClick={async () => { setSyncing(true); await syncNow(); setSyncing(false); }}>
              {syncing ? "Syncing…" : "Sync now"}
            </button>
          </div>
        )}
      </div>
      {me.role === "owner" && <ExportButton />}
      <div className="me"><b>{me.name}</b><SignOut /></div>
    </aside>
  );
}
