// frontend/web/src/components/ChatWindow.jsx
import React, { useState, useRef, useEffect } from "react";
import { sendChat } from "../api";

/**
 * ChatWindow
 * - Handles sending user message, receiving backend response
 * - Accepts both `reply` and `answer` in backend response
 * - Ensures assistant text is visible (explicit styling)
 * - Includes a small toggle to show raw server response for debugging
 */

export default function ChatWindow() {
  const [messages, setMessages] = useState([
    { role: "assistant", text: "Hi — I'm your legal RAG assistant (placeholder)." }
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [rawServerResponse, setRawServerResponse] = useState(null);
  const [showRaw, setShowRaw] = useState(false);
  const sessionIdRef = useRef("session-1");
  const containerRef = useRef(null);

  // scroll to bottom whenever messages change
  useEffect(() => {
    try {
      if (containerRef.current) {
        containerRef.current.scrollTop = containerRef.current.scrollHeight;
      }
    } catch (_) {}
  }, [messages]);

  const postMessage = async () => {
    if (!input.trim()) return;
    const userMsg = { role: "user", text: input.trim() };
    const newMessages = [...messages, userMsg];
    setMessages(newMessages);
    setInput("");
    setLoading(true);
    setRawServerResponse(null);

    try {
      // send the entire conversation (so server can use history if needed)
      const resp = await sendChat(sessionIdRef.current, newMessages, "default");
      // backend may return `reply` or `answer` (we handle both)
      const assistantText = (resp && (resp.reply || resp.answer)) ? (resp.reply || resp.answer) : null;
      const finalText = assistantText && String(assistantText).trim() ? String(assistantText).trim() : "No reply from backend.";
      const assistantMsg = { role: "assistant", text: finalText };
      setMessages(prev => [...prev, assistantMsg]);

      // store raw server response so devs can inspect it
      setRawServerResponse(resp || null);
    } catch (err) {
      console.error("Chat error:", err);
      setMessages(prev => [...prev, { role: "assistant", text: "Error: could not reach backend." }]);
      setRawServerResponse({ error: String(err) });
    } finally {
      setLoading(false);
    }
  };

  const onKey = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      postMessage();
    }
  };

  return (
    <div style={{ maxWidth: 900, margin: "24px auto", borderRadius: 8, overflow: "hidden", boxShadow: "0 6px 24px rgba(0,0,0,0.15)" }}>
      <div style={{ padding: 16, background: "#111827", color: "white" }}>
        <strong>RAG Legal Chat — Demo UI</strong>
        <button
          onClick={() => setShowRaw(s => !s)}
          style={{ marginLeft: 12, padding: "6px 10px", borderRadius: 6, border: "none", cursor: "pointer", background: "#374151", color: "#fff" }}
        >
          {showRaw ? "Hide raw" : "Show raw"}
        </button>
      </div>

      <div
        ref={containerRef}
        style={{ height: 420, overflowY: "auto", padding: 16, background: "#ffffff", color: "#111827" }}
      >
        {messages.map((m, i) => {
          const isUser = (m.role === "user");
          // simple bubble style, enforce readable colors
          const bubbleStyle = {
            maxWidth: "85%",
            marginBottom: 12,
            padding: "10px 14px",
            borderRadius: 12,
            whiteSpace: "pre-wrap",
            lineHeight: 1.5,
            color: isUser ? "#111827" : "#111827", // dark text to ensure visibility on white background
            background: isUser ? "#eef2ff" : "#f3f4f6", // subtle differentiation
            alignSelf: isUser ? "flex-end" : "flex-start"
          };
          return (
            <div key={i} style={{ display: "flex", flexDirection: "column", alignItems: bubbleStyle.alignSelf }}>
              <div style={bubbleStyle}>
                {/* always render m.text so the UI shows the reply */}
                {m.text}
              </div>
            </div>
          );
        })}
        {/* show raw server JSON when toggled - helpful for debugging */}
        {showRaw && rawServerResponse && (
          <pre style={{ marginTop: 16, padding: 12, background: "#111827", color: "#e6e6e6", borderRadius: 8 }}>
            {JSON.stringify(rawServerResponse, null, 2)}
          </pre>
        )}
      </div>

      <div style={{ padding: 12, display: "flex", gap: 8, alignItems: "center", background: "#f9fafb" }}>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKey}
          placeholder="Ask about a statute, case, or regulation..."
          style={{ flex: 1, minHeight: 44, resize: "none", padding: 8, borderRadius: 6, border: "1px solid #e5e7eb" }}
        />
        <button onClick={postMessage} disabled={loading} style={{
          padding: "8px 12px", borderRadius: 6, background: "#4f46e5", color: "white", border: "none", minWidth: 90, cursor: "pointer"
        }}>
          {loading ? "Thinking..." : "Send"}
        </button>
      </div>
    </div>
  );
}
