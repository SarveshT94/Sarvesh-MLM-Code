import { create } from "zustand";
import { checkAuthSession, logoutUser } from "../services/auth";

// 🌐 Enterprise Auth Store (Cookie-Aligned & Secure)
const useAuthStore = create((set) => ({
  user: null,
  isAuthenticated: false,
  isChecking: true, // New: UI can use this to show a loading spinner while verifying

  // 1. Save user profile after successful login
  setAuth: (user) => {
    set({ user, isAuthenticated: true, isChecking: false });
    localStorage.setItem("user", JSON.stringify(user));
  },

  // 2. Securely log out front and back
  logout: async () => {
    // Call the backend to destroy the HttpOnly cookie
    await logoutUser(); 
    
    // Wipe frontend state
    set({ user: null, isAuthenticated: false });
    localStorage.removeItem("user");
    
    // Optional: Redirect to login page
    window.location.href = "/login"; 
  },

  // 3. The "Trust but Verify" Loader
  verifySession: async () => {
    set({ isChecking: true });
    
    // First, grab the cached user for instant UI rendering
    const cachedUser = localStorage.getItem("user");
    if (cachedUser) {
        set({ user: JSON.parse(cachedUser), isAuthenticated: true });
    }

    // Second, silently ask Flask if the cookie is actually still valid
    const session = await checkAuthSession();
    
    if (session.success) {
        // Backend confirms cookie is valid, update state with fresh backend data
        set({ user: session.data.user, isAuthenticated: true, isChecking: false });
        localStorage.setItem("user", JSON.stringify(session.data.user));
    } else {
        // Backend says cookie is dead. Wipe the ghost session!
        set({ user: null, isAuthenticated: false, isChecking: false });
        localStorage.removeItem("user");
    }
  }
}));

export default useAuthStore;
