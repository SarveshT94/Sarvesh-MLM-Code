import axios from "axios";

/*
 * frontend/src/services/api.js — REWRITE
 *
 * Base URL now comes from the environment so the SAME build works in local
 * dev, staging and production (the old file hard-coded http://127.0.0.1:5000,
 * which only works on a developer's own laptop and breaks for every real
 * user). Set NEXT_PUBLIC_API_URL in your deploy environment, e.g.:
 *    NEXT_PUBLIC_API_URL=https://api.yourdomain.com/api
 * Locally it defaults to http://127.0.0.1:5000/api (kept to dodge the IPv6
 * localhost resolution quirk on some machines).
 */
const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:5000/api";

const api = axios.create({
  baseURL: BASE_URL,
  withCredentials: true, // send the session cookie
  headers: { "Content-Type": "application/json" },
  timeout: 15000,
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      if (error.config?.url?.includes("/auth/me")) {
        return Promise.reject(error);
      }
      console.warn("Session expired or unauthorized access.");
      return Promise.reject(error);
    }
    console.error("API Error:", error.response?.status, error.response?.data || error.message);
    return Promise.reject(error);
  }
);

export default api;
