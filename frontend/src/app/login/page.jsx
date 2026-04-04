"use client";

import { useState } from "react";
import { loginUser } from "@/services/auth";
import useAuthStore from "@/store/authStore";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const router = useRouter();
  const setAuth = useAuthStore((state) => state.setAuth);

  // ✅ Aligned with the Backend: Using Email instead of Phone
  const [form, setForm] = useState({
    email: "", 
    password: "",
  });

  const handleLogin = async (e) => {
    e.preventDefault();

    console.log("LOGIN REQUEST DATA:", form);

    // 🔒 Basic validation
    if (!form.email || !form.password) {
      alert("Email and Password required");
      return;
    }

    try {
      const res = await loginUser(form);

      console.log("LOGIN RESPONSE:", res);

      if (res.success) {
        // ✅ Cookie-Aligned: We only save the user profile, no token!
        setAuth(res.data.user);

        alert("Login Successful ✅");
        router.push("/dashboard");
      } else {
        alert(res.message || "Login Failed");
      }
    } catch (err) {
      console.error("LOGIN FRONTEND ERROR:", err);
      alert("Something went wrong");
    }
  };

  return (
    <div className="flex h-screen items-center justify-center bg-gray-100">
      <form
        onSubmit={handleLogin}
        className="p-6 bg-white shadow-lg rounded w-96"
      >
        <h2 className="text-xl font-bold mb-4 text-center">Login</h2>

        {/* ✅ Updated to Email Input */}
        <input
          type="email"
          value={form.email}
          className="border p-2 w-full mb-3 rounded"
          placeholder="Email Address"
          onChange={(e) =>
            setForm({ ...form, email: e.target.value })
          }
        />

        <input
          type="password"
          value={form.password}
          className="border p-2 w-full mb-4 rounded"
          placeholder="Password"
          onChange={(e) =>
            setForm({ ...form, password: e.target.value })
          }
        />

        <button
          type="submit"
          className="bg-blue-500 hover:bg-blue-600 text-white w-full p-2 rounded"
        >
          Login
        </button>
      </form>
    </div>
  );
}
