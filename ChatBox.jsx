import React, { useState, useRef, useEffect } from "react";
import { sendChat } from "../api";
import "./ChatBox.css"; 

/**
 * Utility function to aggressively clean the LLM output string
 */
function cleanText(text) {
    if (!text) return "";
    const cleanupRegex = /[\u0000-\u001f\u007f-\u009f\u200b-\u200f\u2028\u2029\uFEFF]/g;
    return text.replace(cleanupRegex, '').trim();
}


export default function ChatBox() {
    const [messages, setMessages] = useState([
        { role: "assistant", text: "Welcome! Ask me about Indian Law and I will cite the source.", citations: [], debug: {} }
    ]);
    const [input, setInput] = useState("");
    const [loading, setLoading] = useState(false);
    const messagesEndRef = useRef(null);
    const sessionIdRef = useRef("session-1");

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    const handleSend = async () => {
        if (!input.trim() || loading) return;

        // Use 'text' key for consistency with API.jsx mapping
        const userMsg = { role: "user", text: input.trim() };
        
        // 1. Optimistic UI update
        // We use the functional setter to ensure we are appending to the most current state
        setMessages((prev) => [...prev, userMsg]);
        setInput("");
        setLoading(true);

        // 2. IMPORTANT: Get the full history including the message we just added (using the current state)
        const conversationHistory = [...messages, userMsg]; 

        try {
            // This call is now protected in api.jsx against undefined arrays
            const resp = await sendChat(sessionIdRef.current, conversationHistory, "default");

            // 3. Process response
            const rawText = (resp && (resp.reply || resp.answer)) || "No reply from backend.";
            const cleanedText = cleanText(rawText); // Apply aggressive cleanup

            const assistantMsg = {
                role: "assistant",
                text: cleanedText, 
                citations: resp.citations || [],
                debug: resp.debug,
            };

            // 4. Update messages state with the final assistant reply
            setMessages((prev) => {
                const currentMsgs = prev.slice(0, prev.length - 1); // Remove the optimistic user message
                return [...currentMsgs, userMsg, assistantMsg]; 
            });
            
        } catch (err) {
            console.error("Chat error:", err);
            setMessages((prev) => [
                ...prev,
                { role: "assistant", text: "Critical Error: Could not reach the backend API." }
            ]);
        } finally {
            setLoading(false);
        }
    };

    const onKey = (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    const renderMessage = (m, i) => {
        const isUser = m.role === "user";
        const hasCitations = m.citations && m.citations.length > 0;
        
        return (
            <div key={i} className={`message-container ${isUser ? 'user' : 'agent-system'}`}>
                <div className={`message-bubble ${isUser ? 'user-bubble' : 'agent-bubble'}`}>
                    {/* All content uses the 'text' key */}
                    <div className="message-text">{m.text}</div> 

                    {/* Citations Display */}
                    {hasCitations && (
                        <div className="citations-container">
                            <span className="citations-header">Sources Retrieved:</span>
                            <ul className="citation-list">
                                {/* Display unique source IDs only */}
                                {[...new Set(m.citations.map(c => c.source_id))].map((sourceId, idx) => {
                                    const citation = m.citations.find(c => c.source_id === sourceId);
                                    return (
                                        <li key={idx} className="citation-item">
                                            {citation.title || sourceId}
                                        </li>
                                    );
                                })}
                            </ul>
                        </div>
                    )}
                </div>
            </div>
        );
    };

    return (
        <div className="chat-container">
            <header className="chat-header">
                <h1>Legal RAG Agent</h1>
                <p>Sophisticated multi-agent architecture powered by Gemini</p>
            </header>
            
            <div className="message-list">
                {messages.map(renderMessage)}
                {loading && (
                    <div className="message-container agent-system">
                        <div className="message-bubble loading-bubble">
                            <span className="loading-dot">.</span>
                            <span className="loading-dot">.</span>
                            <span className="loading-dot">.</span>
                        </div>
                    </div>
                )}
                <div ref={messagesEndRef} />
            </div>

            <div className="chat-input-form">
                <textarea
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={onKey}
                    placeholder={loading ? "Waiting for response..." : "Ask a legal question..."}
                    className="input-field" 
                    disabled={loading}
                />
                <button onClick={handleSend} disabled={loading}>
                    {loading ? "Thinking..." : "Send"}
                </button>
            </div>
        </div>
    );
}