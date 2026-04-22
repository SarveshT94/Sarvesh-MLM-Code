"use client";

import { useState } from "react";
// 🔥 THE FIX: We import the service wrapper, not the raw axios instance
import { forgotPassword } from "@/services/auth"; 
import Link from "next/link";

export default function ForgotPasswordPage() {
  const [identifier, setIdentifier] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setMessage("");
    setError("");

    if (!identifier) {
      setError("Please enter your email or phone number.");
      return;
    }

    setIsLoading(true);
    
    try {
      // 🔥 THE FIX: Use the clean service function
      const res = await forgotPassword(identifier);
      
      if (res.success) {
        setMessage(res.data.message);
        setIdentifier(""); // Clear the input on success
      } else {
        setError(res.message);
      }
    } catch (err) {
      setError("Secure server connection failed.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center">
        <h2 className="text-3xl font-extrabold text-emerald-600 tracking-tight">
          Reset Password
        </h2>
        <p className="mt-2 text-sm text-slate-500">
          Enter your email or phone number to receive a secure reset link.
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white py-8 px-6 shadow-xl sm:rounded-xl sm:px-10 border border-slate-100">
          
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

          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-1">Email or Phone Number</label>
              <input
                type="text"
                value={identifier}
                className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-emerald-500"
                placeholder="you@example.com or 9876543210"
                onChange={(e) => setIdentifier(e.target.value)}
              />
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-3 px-4 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-lg shadow transition-all disabled:opacity-70 flex justify-center"
            >
              {isLoading ? "Sending..." : "Send Reset Link"}
            </button>
          </form>

          <div className="mt-6 text-center">
            <Link href="/login" className="text-sm font-bold text-emerald-600 hover:text-emerald-500">
              Back to Login
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
