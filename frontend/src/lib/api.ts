import axios from "axios";

function getBaseURL(): string {
  if (typeof window === "undefined") {
    // Server-side (SSR): use internal Docker network URL
    return process.env.INTERNAL_API_URL || "http://backend:8000";
  }
  // Client-side: use browser-accessible URL
  return process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
}

const api = axios.create({
  baseURL: getBaseURL(),
  headers: {
    "Content-Type": "application/json",
  },
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error("API Error:", error.response?.data || error.message);
    return Promise.reject(error);
  }
);

export default api;
