"use client";

import { useEffect } from "react";
import useAuthStore from "@/store/authStore";
import { useRouter } from "next/navigation";

export default function Dashboard() {
  const router = useRouter();

  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);
  const loadUser = useAuthStore((state) => state.loadUser);

  useEffect(() => {
    loadUser();
  }, []);

  useEffect(() => {
    if (!user) {
      router.push("/login");
    }
  }, [user]);

  const handleLogout = () => {
    logout();
    router.push("/login");
  };

  if (!user) {
    return (
      <div className="flex h-screen items-center justify-center text-lg">
        Checking authentication...
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-r from-blue-500 to-indigo-600 flex items-center justify-center">

      <div className="bg-white rounded-2xl shadow-xl p-8 w-full max-w-md">

        <h1 className="text-2xl font-bold text-center text-gray-800 mb-6">
          👋 Welcome, {user.full_name || "User"}
        </h1>

        <div className="space-y-3 text-gray-700">
          <p><strong>📱 Phone:</strong> {user.phone}</p>
          <p><strong>📧 Email:</strong> {user.email || "N/A"}</p>
          <p><strong>🆔 User ID:</strong> {user.id}</p>
          <p><strong>👤 Role:</strong> {user.role_id}</p>
        </div>

        <button
          onClick={handleLogout}
          className="mt-6 w-full bg-red-500 hover:bg-red-600 text-white py-2 rounded-lg transition"
        >
          🚪 Logout
        </button>
      </div>
    </div>
  );
}
