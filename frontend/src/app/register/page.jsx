"use client";

import { useState } from "react";
import { registerUser } from "@/services/auth";
import { useRouter } from "next/navigation";

export default function RegisterPage() {
  const router = useRouter();

  const [form, setForm] = useState({
    full_name: "",
    phone: "",
    password: "",
    referral_code: "",
  });

  const handleRegister = async (e) => {
    e.preventDefault();

    console.log("REGISTER DATA:", form); // 🔥 debug
   
    if (form.phone.includes("@")) {
      alert("Enter valid phone number");
      return;
    }
    const res = await registerUser(form);

    console.log("REGISTER RESPONSE:", res);

    if (res.success) {
      alert("Registered Successfully");
      router.push("/login");
    } else {
      alert(res.message || "Registration Failed");
    }
  };

  return (
    <div className="flex h-screen items-center justify-center">
      <form onSubmit={handleRegister} className="p-6 bg-white shadow rounded w-96">
        <h2 className="text-xl font-bold mb-4">Register</h2>

        <input
          className="border p-2 w-full mb-2"
          placeholder="Full Name"
          onChange={(e) =>
            setForm({ ...form, full_name: e.target.value })
          }
        />

        <input
          className="border p-2 w-full mb-2"
          placeholder="Phone"
          onChange={(e) =>
            setForm({ ...form, phone: e.target.value })
          }
        />

        <input
          type="password"
          className="border p-2 w-full mb-2"
          placeholder="Password"
          onChange={(e) =>
            setForm({ ...form, password: e.target.value })
          }
        />

        <input
          className="border p-2 w-full mb-4"
          placeholder="Referral Code"
          onChange={(e) =>
            setForm({ ...form, referral_code: e.target.value })
          }
        />

        <button
          type="submit"
          className="bg-green-500 text-white w-full p-2"
        >
          Register
        </button>
      </form>
    </div>
  );
}
