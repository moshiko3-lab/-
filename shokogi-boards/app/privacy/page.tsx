import type { Metadata } from "next";

export const metadata: Metadata = { title: "Privacy · Shokogi Boards" };

// Public page (no login), linked from Google's consent screen for "Connect Google Sheets".
export default function PrivacyPage() {
  return (
    <div className="login">
      <article className="panel panel-b privacy">
        <div className="brand"><span className="logo">S</span><div><b>Shokogi</b><small>Board rentals</small></div></div>
        <h1>Privacy</h1>
        <p>Shokogi Boards is the board-rental tool of the Shokogi surf club in Playa Venao, Panama. Only the club&apos;s owner and staff can sign in.</p>
        <h2>What the app keeps</h2>
        <p>Staff accounts, the boards, and the club&apos;s rentals: customer names, phone numbers and optional email or notes, which boards they rented and when. It is used only to run the rentals and is never sold or shared.</p>
        <h2>Google Sheets</h2>
        <p>The owner can connect a Google account to keep a copy of the rentals in Google Sheets. The app then asks only for access to the files it creates itself: a &quot;Shokogi Boards&quot; folder with one spreadsheet. It can&apos;t see or change anything else in that Google Drive, and uses the access only to write the rental tables into that spreadsheet.</p>
        <p>The connection can be removed at any time in the app (Settings, Google Sheets, Disconnect) or in the Google account&apos;s security settings. The spreadsheet stays in the owner&apos;s Drive.</p>
        <h2>Contact</h2>
        <p>Questions: <a className="link" href="mailto:asaf.yizhaky@gmail.com">asaf.yizhaky@gmail.com</a></p>
      </article>
    </div>
  );
}
