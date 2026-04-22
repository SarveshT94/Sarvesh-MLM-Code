"use client";

import { useState, Suspense } from "react";
import { registerUser } from "@/services/auth";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Loader2, Lock } from "lucide-react"; // Added icons for premium UI

// ---------------------------------------------------------
// 📌 THE REGISTRATION FORM (Reads URL Params)
// ---------------------------------------------------------
function RegisterForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  
  // 1. FIXED: Automatically capture the '?ref=' from the URL
  const urlRefCode = searchParams.get("ref") || "";
  const isRefLocked = !!urlRefCode; // If a code exists in the URL, lock the input!

  const [form, setForm] = useState({
    full_name: "",
    email: "",
    phone: "",
    password: "",
    sponsor_id: urlRefCode, // Auto-fill the state
  });

  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [successMsg, setSuccessMsg] = useState("");

  const handleRegister = async (e) => {
    e.preventDefault();
    setErrorMsg("");
    setSuccessMsg("");

    if (!form.full_name || !form.email || !form.phone || !form.password) {
      setErrorMsg("Please fill in all required fields.");
      return;
    }

    if (form.phone.length < 10) {
      setErrorMsg("Please enter a valid 10-digit phone number.");
      return;
    }

    if (form.password.length < 6) {
      setErrorMsg("Password must be at least 6 characters long.");
      return;
    }

    setIsLoading(true);

    try {
      const res = await registerUser(form);

      if (res.success) {
        setSuccessMsg("Registration successful! Redirecting to login...");
        setTimeout(() => {
          router.push("/login");
        }, 2000);
      } else {
        setErrorMsg(res.message || "Registration failed. Please try again.");
      }
    } catch (err) {
      setErrorMsg("Secure server connection failed.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <form onSubmit={handleRegister} className="space-y-5">
      
      {errorMsg && (
        <div className="p-3 bg-red-50 border-l-4 border-red-500 rounded-r-md text-red-700 text-sm font-medium">
          {errorMsg}
        </div>
      )}

      {successMsg && (
        <div className="p-3 bg-emerald-50 border-l-4 border-emerald-500 rounded-r-md text-emerald-700 text-sm font-medium">
          {successMsg}
        </div>
      )}

      {/* Full Name */}
      <div>
        <label className="block text-sm font-semibold text-slate-700 mb-1">Full Name *</label>
        <input
          type="text"
          value={form.full_name}
          className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-500 transition-all"
          placeholder="John Doe"
          onChange={(e) => setForm({ ...form, full_name: e.target.value })}
        />
      </div>

      {/* Email */}
      <div>
        <label className="block text-sm font-semibold text-slate-700 mb-1">Email Address *</label>
        <input
          type="email"
          value={form.email}
          className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-500 transition-all"
          placeholder="you@example.com"
          onChange={(e) => setForm({ ...form, email: e.target.value })}
        />
      </div>

      {/* Phone Number */}
      <div>
        <label className="block text-sm font-semibold text-slate-700 mb-1">Phone Number *</label>
        <input
          type="tel"
          value={form.phone}
          className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-500 transition-all"
          placeholder="9876543210"
          onChange={(e) => setForm({ ...form, phone: e.target.value.replace(/\D/g, '') })}
        />
      </div>

      {/* Password */}
      <div>
        <label className="block text-sm font-semibold text-slate-700 mb-1">Secure Password *</label>
        <input
          type="password"
          value={form.password}
          className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-500 transition-all"
          placeholder="••••••••"
          onChange={(e) => setForm({ ...form, password: e.target.value })}
        />
      </div>

      {/* Referral / Sponsor Code */}
      <div>
        <div className="flex justify-between items-center mb-1">
          <label className="block text-sm font-semibold text-slate-700">
            Referral Code {isRefLocked ? "" : "(Optional)"}
          </label>
          {isRefLocked && (
            <span className="text-xs font-bold text-emerald-600 flex items-center bg-emerald-50 px-2 py-0.5 rounded border border-emerald-100">
              <Lock className="h-3 w-3 mr-1" /> Sponsor Locked
            </span>
          )}
        </div>
        <input
          type="text"
          value={form.sponsor_id}
          readOnly={isRefLocked} // 2. FIXED: Prevents editing if auto-filled
          className={`w-full px-4 py-2.5 border rounded-lg text-slate-900 uppercase transition-all ${
            isRefLocked 
              ? "bg-slate-100 border-slate-200 text-slate-500 cursor-not-allowed focus:outline-none" 
              : "bg-slate-50 border-slate-200 focus:outline-none focus:ring-2 focus:ring-emerald-500"
          }`}
          placeholder="ABC12345"
          onChange={(e) => setForm({ ...form, sponsor_id: e.target.value.toUpperCase() })}
        />
      </div>

      <button
        type="submit"
        disabled={isLoading || successMsg !== ""}
        className="w-full py-3 px-4 mt-2 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-lg shadow-md hover:shadow-lg transition-all disabled:opacity-70 disabled:cursor-not-allowed flex items-center justify-center"
      >
        {isLoading ? (
          <Loader2 className="h-5 w-5 animate-spin text-white" />
        ) : (
          "Create Account"
        )}
      </button>
    </form>
  );
}

// ---------------------------------------------------------
// 📌 PAGE LAYOUT (Wraps Form in Next.js Suspense)
// ---------------------------------------------------------
export default function RegisterPage() {
  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-center py-12 px-4 sm:px-6 lg:px-8">
      
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center">
        <h2 className="text-4xl font-extrabold text-emerald-600 tracking-tight">
          Join RK trendz
        </h2>
        <p className="mt-3 text-sm text-slate-500 font-medium">
          Create your secure MLM account today
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white py-8 px-6 shadow-2xl sm:rounded-xl sm:px-10 border border-slate-100">
          
          {/* 3. FIXED: Suspense boundary for useSearchParams */}
          <Suspense fallback={
            <div className="flex justify-center items-center py-10">
              <Loader2 className="h-8 w-8 animate-spin text-emerald-600" />
            </div>
          }>
            <RegisterForm />
          </Suspense>

          <div className="mt-6 text-center">
            <p className="text-sm text-slate-600">
              Already have an account?{" "}
              <Link href="/login" className="font-bold text-emerald-600 hover:text-emerald-500 transition-colors">
                Log in here
              </Link>
            </p>
          </div>

        </div>
      </div>
    </div>
  );
}
