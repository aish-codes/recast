"use client";

import { useState } from "react";

export default function Login() {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const res = await fetch("/api/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
    setBusy(false);
    if (res.ok) window.location.href = "/";
    else setError("That password didn't match.");
  }

  return (
    <main className="grid min-h-screen place-items-center p-6">
      <form onSubmit={submit} className="w-full max-w-sm space-y-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">recast</h1>
          <p className="mt-1 text-sm text-muted">Your resumes live behind this.</p>
        </div>
        <input
          type="password"
          autoFocus
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
          className="w-full rounded border border-line bg-surface px-3 py-2 outline-none
                     focus:border-accent"
        />
        {error && <p className="text-sm text-bad">{error}</p>}
        <button
          disabled={busy || !password}
          className="w-full rounded bg-accent px-3 py-2 text-sm font-medium text-white
                     disabled:opacity-40"
        >
          {busy ? "Checking…" : "Enter"}
        </button>
      </form>
    </main>
  );
}
