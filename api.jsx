// frontend/web/src/api.jsx
import axios from "axios";

// NOTE: Update this to your final Render URL upon deployment
const API_BASE = "http://127.0.0.1:8000";

/**
 * sendChat - Maps frontend content to backend 'text' key and handles errors.
 * @param {string} session_id
 * @param {Array} messages - array of { role, text } (or {role, content})
 * @param {string} mode - optional
 * @returns {Object} server response {reply, citations, debug}
 */
export async function sendChat(session_id, messages, mode = "default") {
  
  // FIX: Map content/text key to the backend's expected key, 'text'. 
  // Use messages || [] to prevent the "cannot read map of undefined" error if messages state is temporarily null.
  const backendMessages = (messages || []).map(m => ({
    role: m.role,
    // Use 'text' or fallback to 'content', which should contain the string value
    text: m.text || m.content 
  }));
  
  const body = {
    session_id,
    messages: backendMessages, // Use the cleaned array
    mode,
  };

  try {
    const res = await axios.post(`${API_BASE}/chat`, body, {
      headers: { "Content-Type": "application/json" },
      timeout: 30000,
    });
    return res.data;
  } catch (err) {
    // Robust error handling to prevent frontend crashes
    if (err.response) {
      return {
        error: true,
        status: err.response.status,
        message: err.response.data || err.response.statusText || "Server returned an error.",
      };
    } else if (err.request) {
      return { error: true, message: "No response from server (network or server down)." };
    } else {
      return { error: true, message: err.message || "Unknown request error." };
    }
  }
}

/**
 * retrieve - simple wrapper for retrieval endpoint
 */
export async function retrieve(query) {
  try {
    const res = await axios.post(`${API_BASE}/retrieve`, { query, k: 4 }, {
      headers: { "Content-Type": "application/json" }
    });
    return res.data;
  } catch (err) {
    return { error: true, message: "Failed to retrieve" };
  }
}