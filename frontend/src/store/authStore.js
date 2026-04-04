import { create } from "zustand";

// 🌐 Enterprise Auth Store (Cookie-Aligned)
const useAuthStore = create((set) => ({
  user: null,
  isAuthenticated: false, // Helpful flag for your UI to check if someone is logged in

  // 1. Save the user profile data (Browser handles the actual security cookie)
  setAuth: (user) => {
    set({ user, isAuthenticated: true });
    localStorage.setItem("user", JSON.stringify(user));
  },

  // 2. Wipe the profile data on logout
  logout: () => {
    set({ user: null, isAuthenticated: false });
    localStorage.removeItem("user");
  },

  // 3. Instantly reload the user profile when they refresh the Next.js page
  loadUser: () => {
    const userStr = localStorage.getItem("user");
    if (userStr) {
      try {
        const user = JSON.parse(userStr);
        set({ user, isAuthenticated: true });
      } catch (error) {
        // If the localStorage data gets corrupted, wipe it safely
        localStorage.removeItem("user");
        set({ user: null, isAuthenticated: false });
      }
    }
  }
}));

export default useAuthStore;
