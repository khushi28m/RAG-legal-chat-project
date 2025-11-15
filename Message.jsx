import React from "react";

export default function Message({ msg }) {
    const isUser = msg.role === "user";
    // Check for msg.citations and msg.debug (if used)
    const hasCitations = msg.citations && msg.citations.length > 0;
    
    // Determine content: uses msg.text for simplicity, assuming upstream state handles reply/content cleanup.
    const messageContent = msg.text || msg.content; 

    // Simple Bubble Styles for display
    const bubbleStyle = {
        maxWidth: "85%",
        background: isUser ? "#4f46e5" : "#f3ff", // User: Indigo, Assistant: Light Gray
        color: isUser ? "white" : "#111827",       // Text Color
        padding: "10px 14px",
        borderRadius: "12px 12px 12px 0",          // Subtle curvature
        whiteSpace: "pre-wrap",
        boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
        // Override border-radius based on role
        borderBottomLeftRadius: isUser ? "12px" : "0", 
        borderBottomRightRadius: isUser ? "0" : "12px", 
    };

    return (
        <div style={{
            display: "flex",
            justifyContent: isUser ? "flex-end" : "flex-start",
            padding: "6px 10px",
            alignItems: "flex-end"
        }}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: isUser ? "flex-end" : "flex-start" }}>
                <div style={bubbleStyle}>
                    {/* The core message content */}
                    {messageContent}
                </div>

                {/* CITATION DISPLAY BLOCK */}
                {hasCitations && (
                    <div style={{ 
                        marginTop: 4, 
                        marginBottom: 8,
                        padding: "4px 8px", 
                        background: isUser ? "#3e37c4" : "#e0e0e0", 
                        color: isUser ? "#fff" : "#333",
                        fontSize: 10, 
                        borderRadius: 6,
                        maxWidth: "100%",
                        borderTopRightRadius: isUser ? 0 : 6,
                        borderTopLeftRadius: isUser ? 6 : 0,
                    }}>
                        <strong style={{ display: "block", marginBottom: 2 }}>Sources:</strong>
                        <ul style={{ listStyle: "disc", marginLeft: 15, padding: 0, margin: 0, lineHeight: 1.3 }}>
                            {/* Display unique source IDs only for cleaner view */}
                            {[...new Set(msg.citations.map(c => c.source_id))].map((sourceId, idx) => {
                                const citation = msg.citations.find(c => c.source_id === sourceId);
                                return (
                                    <li key={idx} style={{ padding: 0 }}>
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
}