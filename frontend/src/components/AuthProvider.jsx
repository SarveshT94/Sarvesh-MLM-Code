"use client";

import { useEffect, useRef } from "react";
import useAuthStore from "@/store/authStore";

export default function AuthProvider({ children }) {
  const { verifySession, isChecking } = useAuthStore();
  const hasChecked = useRef(false); // Prevents infinite loops!

  useEffect(() => {
    if (!hasChecked.current) {
      verifySession();
      hasChecked.current = true;
    }
  }, [verifySession]);

  if (isChecking) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-slate-50">
        <div className="h-12 w-12 animate-spin rounded-full border-4 border-emerald-600 border-t-transparent"></div>
      </div>
    );
  }

  return <>{children}</>;
}
