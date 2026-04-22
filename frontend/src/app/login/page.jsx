"use client";

import { useState } from "react";
import { loginUser } from "@/services/auth";
import useAuthStore from "@/store/authStore";
import { useRouter } from "next/navigation";
import Link from "next/link";

export default function LoginPage() {
  const router = useRouter();
  const setAuth = useAuthStore((state) => state.setAuth);

  // 1. FIXED: State now uses 'identifier' to capture either email or phone
  const [form, setForm] = useState({ identifier: "", password: "" });
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  const handleLogin = async (e) => {
    e.preventDefault();
    setErrorMsg("");

    // 2. FIXED: Validation now checks for identifier
    if (!form.identifier || !form.password) {
      setErrorMsg("Please enter both email/phone and password.");
      return;
    }

    setIsLoading(true);

    try {
      const res = await loginUser(form);

      if (res.success) {
        setAuth(res.data.user);
        router.push("/dashboard");
      } else {
        setErrorMsg(res.message || "Invalid credentials.");
      }
    } catch (err) {
      setErrorMsg("Secure server connection failed. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-center py-12 px-4 sm:px-6 lg:px-8">

      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center">
        <h2 className="text-4xl font-extrabold text-emerald-600 tracking-tight">
          Welcome to RK trendz
        </h2>
        <p className="mt-3 text-sm text-slate-500 font-medium">
          Sign in to access your secure dashboard
        </p>
      </div>
      
      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white py-8 px-6 shadow-2xl sm:rounded-xl sm:px-10 border border-slate-100">

          {errorMsg && (
            <div className="mb-5 p-3 bg-red-50 border-l-4 border-red-500 rounded-r-md text-red-700 text-sm font-medium">
              {errorMsg}
            </div>
          )}

          <form onSubmit={handleLogin} className="space-y-6">
            <div>
              {/* 3. FIXED: Label, type, value, placeholder, and onChange updated for 'identifier' */}
              <label className="block text-sm font-semibold text-slate-700 mb-2">
                Email or Phone Number
              </label>
              <input
                type="text"
                value={form.identifier}
                className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition-all"
                placeholder="admin@rktrendz.com or 9876543210"
                onChange={(e) => setForm({ ...form, identifier: e.target.value })}
              />
            </div>

            <div>
              <div className="flex justify-between items-center mb-2">
                <label className="block text-sm font-semibold text-slate-700">
                  Password
                </label>
                {/* 🔥 PERMANENT FIX: The active Next.js Link to the recovery page */}
                <Link href="/forgot-password" className="text-sm font-medium text-emerald-600 hover:text-emerald-500 transition-colors">
                  Forgot Password?
                </Link>
              </div>
              <input
                type="password"
                value={form.password}
                className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition-all"
                placeholder="••••••••"
                onChange={(e) => setForm({ ...form, password: e.target.value })}
              />
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-3 px-4 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-lg shadow-md hover:shadow-lg transition-all disabled:opacity-70 disabled:cursor-not-allowed flex items-center justify-center"
            >
              {isLoading ? (
                <div className="h-5 w-5 animate-spin rounded-full border-2 border-white border-t-transparent"></div>
              ) : (
                "Secure Login"
              )}
            </button>
          </form>
          
          <div className="mt-8 text-center">
            <p className="text-sm text-slate-600">
              Don't have an account?{" "}
              <Link href="/register" className="font-bold text-emerald-600 hover:text-emerald-500 transition-colors">
                Register here
              </Link>
            </p>
          </div>

        </div>
      </div>
    </div>
  );
}
