"use client";

import { useState, Suspense } from "react";
import { resetPassword } from "@/services/auth";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";

// ⚠️ Next.js 14 requires components using useSearchParams to be wrapped in Suspense
function ResetPasswordForm() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  const router = useRouter();

  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setMessage("");
    setError("");

    if (!token) {
      setError("Invalid or missing reset token.");
      return;
    }
    if (password.length < 6) {
      setError("Password must be at least 6 characters long.");
      return;
    }

    setIsLoading(true);
    const res = await resetPassword(token, password);

    if (res.success) {
      setMessage("Password successfully reset! Redirecting to login...");
      setTimeout(() => router.push("/login"), 3000);
    } else {
      setError(res.message);
    }
    setIsLoading(false);
  };

  if (!token) {
    return (
      <div className="text-center p-6 bg-red-50 text-red-700 rounded-lg">
        <p className="font-bold">Invalid Link</p>
        <p className="text-sm mt-2">This password reset link is missing a secure token.</p>
        <Link href="/forgot-password" className="mt-4 inline-block text-emerald-600 font-bold hover:underline">
          Request a new link
        </Link>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {error && (
        <div className="mb-4 p-3 bg-red-50 border-l-4 border-red-500 text-red-700 text-sm font-medium">
          {error}
        </div>
      )}
      {message && (
        <div className="mb-4 p-3 bg-emerald-50 border-l-4 border-emerald-500 text-emerald-700 text-sm font-medium">
          {message}
        </div>
      )}

      <div>
        <label className="block text-sm font-semibold text-slate-700 mb-1">New Password</label>
        <input
          type="password"
          value={password}
          className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-emerald-500"
          placeholder="••••••••"
          onChange={(e) => setPassword(e.target.value)}
        />
      </div>

      <button
        type="submit"
        disabled={isLoading || message !== ""}
        className="w-full py-3 px-4 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-lg shadow transition-all disabled:opacity-70 flex justify-center"
      >
        {isLoading ? "Saving..." : "Save New Password"}
      </button>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center">
        <h2 className="text-3xl font-extrabold text-emerald-600 tracking-tight">Create New Password</h2>
        <p className="mt-2 text-sm text-slate-500">Please enter your new secure password below.</p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white py-8 px-6 shadow-xl sm:rounded-xl sm:px-10 border border-slate-100">
          <Suspense fallback={<div className="text-center text-slate-500">Loading secure token...</div>}>
            <ResetPasswordForm />
          </Suspense>
        </div>
      </div>
    </div>
  );
}
