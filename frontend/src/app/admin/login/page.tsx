"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import { saveAdminCredentials } from "@/lib/admin-auth";

export default function AdminLoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const reason = searchParams.get("reason");

  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("adminpass");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiBase}/api/admin/dashboard?hours=6`, {
        cache: "no-store",
        headers: {
          "X-Admin-User": username,
          "X-Admin-Password": password,
        },
      });

      if (!res.ok) {
        throw new Error("Invalid admin credentials");
      }

      saveAdminCredentials({ username, password });
      router.push("/admin");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to sign in");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 p-6 md:p-10">
      <div className="max-w-md mx-auto pt-10">
        <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6 md:p-8 space-y-5 shadow-xl shadow-slate-950/40">
          <div className="space-y-2">
            <p className="text-xs uppercase tracking-[0.25em] text-indigo-300">Admin Access</p>
            <h1 className="text-2xl font-semibold">Sign in to Dashboard</h1>
            <p className="text-sm text-slate-400">
              Authenticate to view system health, status logs, and analytics.
            </p>
          </div>

          {reason === "expired" && (
            <p className="text-amber-300 text-sm rounded border border-amber-800/40 bg-amber-950/30 p-2">
              Session expired or invalid. Please sign in again.
            </p>
          )}

          {error && (
            <p className="text-red-300 text-sm rounded border border-red-800/40 bg-red-950/30 p-2">
              {error}
            </p>
          )}

          <form onSubmit={handleSubmit} className="space-y-3">
            <input
              className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Admin username"
              autoComplete="username"
              required
            />
            <input
              type="password"
              className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Admin password"
              autoComplete="current-password"
              required
            />
            <button
              type="submit"
              disabled={submitting}
              className="w-full rounded bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-800 px-4 py-2 font-medium"
            >
              {submitting ? "Signing in..." : "Sign in"}
            </button>
          </form>

          <div className="text-sm text-slate-400 flex items-center justify-between">
            <span>CRM Digital FTE</span>
            <Link href="/" className="text-indigo-300 hover:text-indigo-200">
              Back to Web Intake
            </Link>
          </div>
        </div>
      </div>
    </main>
  );
}
