import axios from "axios";

// 🌐 Enterprise API Bridge
const API = axios.create({
  baseURL: "http://127.0.0.1:5000/api",
  
  // 🔥 THE MAGIC KEY: This tells the browser to automatically attach 
  // the secure Flask-Login session cookie to every request.
  withCredentials: true, 
  
  headers: {
    "Content-Type": "application/json"
  }
});

/* Notice: We completely deleted the Interceptor! 
  Because we are using secure HttpOnly cookies, we don't need to manually 
  attach tokens anymore. The browser does it automatically and invisibly. 
*/

export default API;
