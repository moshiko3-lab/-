"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { loginEmail } from "@/lib/login";

export default function LoginPage() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    setBusy(true);
    setError("");
    const { error } = await createClient().auth.signInWithPassword({
      email: loginEmail(String(form.get("login"))),
      password: String(form.get("password")),
    });
    if (error) {
      setBusy(false);
      setError(error.code === "invalid_credentials" ? "Wrong username, email or password."
        : error.code === "user_banned" ? "This account is deactivated. Ask the owner."
        : "Couldn't sign in. Check the connection and try again.");
      return;
    }
    router.replace("/");
    router.refresh();
  }

  return (
    <div className="login">
      <form onSubmit={onSubmit}>
        <div className="brand">
          <span className="logo">S</span>
          <div><b>Shokogi</b><small>Board rentals</small></div>
        </div>
        <label>
          <span className="label">Username or email</span>
          <input name="login" autoComplete="username" autoCapitalize="none" autoCorrect="off" spellCheck={false} required autoFocus />
        </label>
        <label>
          <span className="label">Password</span>
          <input name="password" type="password" autoComplete="current-password" required />
        </label>
        {error && <p className="error" role="alert">{error}</p>}
        <button className="btn primary" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
      </form>
    </div>
  );
}
