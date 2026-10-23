"use client";

// First login with a temporary password (or after the owner reset it): choose your own before anything else.
import { useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import SignOut from "./SignOut";

export default function ChangePassword({ name }: { name: string }) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const password = String(f.get("password"));
    if (password.length < 8) return setError("The password needs at least 8 characters.");
    if (password !== f.get("again")) return setError("The two passwords don't match.");
    setBusy(true);
    const db = createClient();
    const { error } = await db.auth.updateUser({ password });
    if (error) {
      setBusy(false);
      return setError(error.code === "same_password" ? "Choose a password different from the temporary one." : "Couldn't save the password. Try again.");
    }
    await db.rpc("password_changed");
    router.refresh();
  }

  return (
    <div className="login">
      <form onSubmit={onSubmit}>
        <div className="brand"><span className="logo">S</span><div><b>Shokogi</b><small>Board rentals</small></div></div>
        <p className="muted" style={{ margin: 0 }}>Welcome, {name}. Choose your own password to continue.</p>
        <label><span className="label">New password</span><input name="password" type="password" autoComplete="new-password" required autoFocus /></label>
        <label><span className="label">Repeat it</span><input name="again" type="password" autoComplete="new-password" required /></label>
        {error && <p className="error" role="alert">{error}</p>}
        <button className="btn primary" disabled={busy}>{busy ? "Saving…" : "Save password"}</button>
        <SignOut />
      </form>
    </div>
  );
}
