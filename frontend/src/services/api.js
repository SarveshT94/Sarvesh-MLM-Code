import axios from "axios";

// 🌐 Enterprise API Bridge
const API = axios.create({
  // 🔥 FIXED: Use relative path so Next.js rewrites can catch it and proxy it.
  baseURL: "/api",

  // The browser automatically attaches the secure Flask-Login session cookie
  withCredentials: true,

  headers: {
    "Content-Type": "application/json"
  }
});

export default API;
