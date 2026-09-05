import axios from "axios";

// 🔥 Force 127.0.0.1 to bypass the IPv6 localhost resolution bug
const api = axios.create({
  baseURL: "http://127.0.0.1:5000/api", 
  withCredentials: true, // Crucial for keeping the user logged in
  headers: {
    "Content-Type": "application/json",
  }
});

// Global Response Interceptor
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // 1. Check if the error is a 401 Unauthorized
    if (error.response?.status === 401) {
      // If it's just the initial auth check, stay quiet. It's normal.
      if (error.config?.url?.includes('/auth/me')) {
        return Promise.reject(error);
      }
      // If it's a real unauthorized action, log a soft warning, not a red error.
      console.warn("Session expired or unauthorized access.");
      return Promise.reject(error);
    }

    // 2. Only log actual critical errors (like 500 Server Errors or 404 Not Found)
    console.error("API Error:", error.response?.status, error.response?.data || error.message);
    return Promise.reject(error);
  }
);

export default api;
