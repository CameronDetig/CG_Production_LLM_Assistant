import { useCallback, useEffect, useRef, useState } from "react";
import {
  Aperture,
  ChevronDown,
  CircleAlert,
  ImagePlus,
  LogIn,
  LogOut,
  Menu,
  MessageSquarePlus,
  RefreshCw,
  Send,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { beginLogin, completeLogin, loadConfig, logout, readSession } from "./auth";
import {
  deleteConversation,
  getConversation,
  imageToBase64,
  listConversations,
  streamChat,
} from "./api";
import type {
  ConversationSummary,
  DetailBlock,
  Message,
  RuntimeConfig,
  SSEMessage,
  Session,
  Thumbnail,
} from "./types";

const suggestions = [
  "Show me character assets with available thumbnails",
  "Find Blender files related to environment lighting",
  "How many image assets are in each production?",
];

function Detail({ block }: { block: DetailBlock }) {
  const labels = {
    enhanced_query: "Interpreted request",
    sql_query: `SQL query${block.data.attempt ? ` · attempt ${block.data.attempt}` : ""}`,
    query_results: `Query results · ${block.data.count ?? 0} found`,
    retry_feedback: "Query retry",
  };
  return (
    <details className="detail-card">
      <summary><ChevronDown size={15} />{labels[block.type]}</summary>
      {block.type === "sql_query" ? (
        <pre><code>{String(block.data.query ?? "")}</code></pre>
      ) : block.type === "query_results" ? (
        <ResultTable rows={(block.data.results as Record<string, unknown>[]) ?? []} />
      ) : (
        <p>{String(block.data.query ?? block.data.feedback ?? "")}</p>
      )}
    </details>
  );
}

function ResultTable({ rows }: { rows: Record<string, unknown>[] }) {
  if (!rows.length) return <p className="muted">No preview rows returned.</p>;
  const columns = Object.keys(rows[0]).filter((key) => !["thumbnail_url", "thumbnail_path"].includes(key));
  return (
    <div className="table-scroll">
      <table>
        <thead><tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr></thead>
        <tbody>{rows.map((row, index) => (
          <tr key={index}>{columns.map((column) => <td key={column}>{String(row[column] ?? "")}</td>)}</tr>
        ))}</tbody>
      </table>
    </div>
  );
}

function MessageCard({ message }: { message: Message }) {
  return (
    <article className={`message ${message.role} ${message.error ? "message-error" : ""}`}>
      <div className="message-avatar">{message.role === "user" ? "YOU" : <Sparkles size={17} />}</div>
      <div className="message-body">
        <div className="message-label">{message.role === "user" ? "You" : "Assistant"}</div>
        {message.imageUrl && <img className="upload-preview-inline" src={message.imageUrl} alt="Uploaded search reference" />}
        {message.pending && !message.content ? <div className="thinking"><i /><i /><i /></div> : (
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
        )}
        {message.details?.map((detail, index) => <Detail key={`${detail.type}-${index}`} block={detail} />)}
        {!!message.thumbnails?.length && (
          <div className="thumbnail-grid">
            {message.thumbnails.map((thumbnail, index) => (
              <a href={thumbnail.thumbnail_url} target="_blank" rel="noreferrer" key={`${thumbnail.file_id}-${index}`}>
                <img src={thumbnail.thumbnail_url} alt={thumbnail.file_name || "Production asset thumbnail"} />
                <span>{thumbnail.file_name || thumbnail.file_type || "Asset"}</span>
              </a>
            ))}
          </div>
        )}
      </div>
    </article>
  );
}

export default function App() {
  const [config, setConfig] = useState<RuntimeConfig | null>(null);
  const [session, setSession] = useState<Session | null>(readSession());
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [text, setText] = useState("");
  const [image, setImage] = useState<{ data: string; preview: string; name: string } | null>(null);
  const [status, setStatus] = useState("Ready");
  const [busy, setBusy] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  const expireSession = useCallback(() => {
    sessionStorage.removeItem("cg-assistant.session");
    setSession(null);
    setError("Your session expired. Sign in again to continue.");
  }, []);

  const refreshConversations = useCallback(async (runtime = config) => {
    if (!runtime || !readSession()) return;
    try {
      setConversations(await listConversations(runtime));
    } catch (reason) {
      if (reason instanceof Error && reason.message === "SESSION_EXPIRED") expireSession();
      else setError(reason instanceof Error ? reason.message : "Unable to load conversations");
    }
  }, [config, expireSession]);

  useEffect(() => {
    void (async () => {
      try {
        const runtime = await loadConfig();
        setConfig(runtime);
        if (window.location.pathname === "/auth/callback") {
          const signedIn = await completeLogin(runtime);
          setSession(signedIn);
        }
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : "Unable to initialize the application");
      }
    })();
  }, []);

  useEffect(() => { if (config && session) void refreshConversations(config); }, [config, session, refreshConversations]);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, status]);

  const selectConversation = async (id: string) => {
    if (!config || busy) return;
    setConversationId(id);
    setSidebarOpen(false);
    setStatus("Loading conversation");
    try {
      setMessages(await getConversation(config, id));
      setStatus("Ready");
    } catch (reason) {
      if (reason instanceof Error && reason.message === "SESSION_EXPIRED") expireSession();
      else setError(reason instanceof Error ? reason.message : "Unable to load conversation");
      setStatus("Error");
    }
  };

  const newConversation = () => {
    abortRef.current?.abort();
    setConversationId(null);
    setMessages([]);
    setStatus("Ready");
    setSidebarOpen(false);
  };

  const removeConversation = async (id: string) => {
    if (!config || !confirm("Delete this conversation? This cannot be undone.")) return;
    try {
      await deleteConversation(config, id);
      if (conversationId === id) newConversation();
      await refreshConversations();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to delete conversation");
    }
  };

  const updateAssistant = (mutate: (message: Message) => Message) => {
    setMessages((current) => current.map((message, index) => index === current.length - 1 ? mutate(message) : message));
  };

  const handleEvent = (event: SSEMessage) => {
    if (event.event === "agent_start") {
      if (typeof event.data.conversation_id === "string") setConversationId(event.data.conversation_id);
      return;
    }
    if (event.event === "status") {
      setStatus(String(event.data.message ?? "Working"));
      return;
    }
    if (["enhanced_query", "sql_query", "query_results", "retry_feedback"].includes(event.event)) {
      updateAssistant((message) => ({
        ...message,
        details: [...(message.details ?? []), { type: event.event as DetailBlock["type"], data: event.data }],
      }));
      return;
    }
    if (event.event === "thumbnail") {
      updateAssistant((message) => ({ ...message, thumbnails: [...(message.thumbnails ?? []), event.data as unknown as Thumbnail] }));
      return;
    }
    if (event.event === "answer_start") {
      setStatus("Writing answer");
      updateAssistant((message) => ({ ...message, pending: false }));
      return;
    }
    if (event.event === "answer_chunk") {
      updateAssistant((message) => ({ ...message, content: message.content + String(event.data.text ?? ""), pending: false }));
      return;
    }
    if (event.event === "error") {
      updateAssistant((message) => ({ ...message, content: String(event.data.message ?? "Request failed"), pending: false, error: true }));
      setStatus("Error");
      return;
    }
    if (event.event === "done") setStatus(event.data.failed ? "Request failed" : "Ready");
  };

  const send = async (override?: string) => {
    const query = (override ?? text).trim() || (image ? "Find similar images to the uploaded image" : "");
    if (!query || !config || !session || busy) return;
    setError(null);
    setBusy(true);
    setText("");
    const submittedImage = image;
    setImage(null);
    setMessages((current) => [
      ...current,
      { role: "user", content: query, imageUrl: submittedImage?.preview },
      { role: "assistant", content: "", pending: true, details: [], thumbnails: [] },
    ]);
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      await streamChat(config, {
        query,
        ...(conversationId ? { conversation_id: conversationId } : {}),
        ...(submittedImage ? { uploaded_image_base64: submittedImage.data } : {}),
      }, handleEvent, controller.signal);
      await refreshConversations();
    } catch (reason) {
      if (reason instanceof DOMException && reason.name === "AbortError") return;
      if (reason instanceof Error && reason.message === "SESSION_EXPIRED") expireSession();
      else updateAssistant((message) => ({ ...message, content: reason instanceof Error ? reason.message : "Request failed", pending: false, error: true }));
      setStatus("Error");
    } finally {
      setBusy(false);
      abortRef.current = null;
    }
  };

  const chooseImage = async (file?: File) => {
    if (!file) return;
    try {
      const resized = await imageToBase64(file);
      setImage({ ...resized, name: file.name });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to process image");
    }
  };

  if (!session) {
    return (
      <main className="login-shell">
        <div className="login-glow" />
        <section className="login-card">
          <div className="brand-mark"><Aperture size={27} /><span>CG</span></div>
          <p className="eyebrow">Production intelligence</p>
          <h1>Your studio archive,<br /><em>ready to answer.</em></h1>
          <p className="login-copy">Search production assets, inspect metadata, and find visual references through one focused workspace.</p>
          {error && <div className="alert"><CircleAlert size={18} />{error}</div>}
          <button className="primary large" disabled={!config} onClick={() => config && void beginLogin(config)}>
            <LogIn size={18} /> Continue to secure sign in
          </button>
          <p className="fine-print">Authentication is handled by Amazon Cognito. Your password is never sent to this site.</p>
        </section>
      </main>
    );
  }

  return (
    <div className="app-shell">
      <aside className={sidebarOpen ? "sidebar open" : "sidebar"}>
        <div className="sidebar-head">
          <div className="wordmark"><Aperture size={24} /><span>CG Assistant</span></div>
          <button className="icon-button mobile-only" onClick={() => setSidebarOpen(false)} aria-label="Close navigation"><X /></button>
        </div>
        <button className="new-chat" onClick={newConversation}><MessageSquarePlus size={18} />New conversation</button>
        <div className="section-label"><span>Conversations</span><button className="icon-button" onClick={() => void refreshConversations()} aria-label="Refresh conversations"><RefreshCw size={15} /></button></div>
        <nav className="conversation-list" aria-label="Conversations">
          {conversations.map((conversation) => (
            <div className={`conversation-row ${conversationId === conversation.conversation_id ? "active" : ""}`} key={conversation.conversation_id}>
              <button onClick={() => void selectConversation(conversation.conversation_id)}>
                <span>{conversation.title}</span><small>{conversation.message_count} messages</small>
              </button>
              <button className="delete-button" onClick={() => void removeConversation(conversation.conversation_id)} aria-label={`Delete ${conversation.title}`}><Trash2 size={14} /></button>
            </div>
          ))}
          {!conversations.length && <p className="sidebar-empty">Your conversations will appear here.</p>}
        </nav>
        <div className="account-card">
          <div className="account-avatar">{(session.email ?? "U").slice(0, 1).toUpperCase()}</div>
          <div><strong>{session.email ?? "Signed in"}</strong><span>Production access</span></div>
          <button className="icon-button" onClick={() => config && logout(config)} aria-label="Sign out"><LogOut size={17} /></button>
        </div>
      </aside>
      {sidebarOpen && <button className="backdrop" onClick={() => setSidebarOpen(false)} aria-label="Close navigation" />}

      <main className="workspace">
        <header className="topbar">
          <button className="icon-button mobile-only" onClick={() => setSidebarOpen(true)} aria-label="Open navigation"><Menu /></button>
          <div><span className={`status-dot ${busy ? "working" : ""}`} />{status}</div>
          <span className="collection-label">Blender Studio archive</span>
        </header>
        <section className="chat-scroll" aria-live="polite">
          {!messages.length ? (
            <div className="empty-state">
              <div className="empty-icon"><Sparkles /></div>
              <p className="eyebrow">Connected to production data</p>
              <h2>What are you looking for?</h2>
              <p>Ask naturally about files, shows, formats, metadata, or visual similarity.</p>
              <div className="suggestions">{suggestions.map((suggestion) => <button key={suggestion} onClick={() => void send(suggestion)}>{suggestion}<Send size={14} /></button>)}</div>
            </div>
          ) : messages.map((message, index) => <MessageCard key={index} message={message} />)}
          <div ref={endRef} />
        </section>
        <footer className="composer-wrap">
          {error && <div className="toast"><CircleAlert size={16} /><span>{error}</span><button onClick={() => setError(null)} aria-label="Dismiss"><X size={15} /></button></div>}
          {image && <div className="image-chip"><img src={image.preview} alt="Selected upload" /><span>{image.name}</span><button onClick={() => setImage(null)} aria-label="Remove image"><X size={15} /></button></div>}
          <div className="composer">
            <label className="upload-button" title="Add a reference image">
              <ImagePlus size={20} /><input type="file" accept="image/*" onChange={(event) => void chooseImage(event.target.files?.[0])} />
            </label>
            <textarea value={text} onChange={(event) => setText(event.target.value)} onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void send(); }
            }} placeholder="Ask about production assets…" rows={1} disabled={busy} aria-label="Message" />
            <button className="send-button" onClick={() => void send()} disabled={busy || (!text.trim() && !image)} aria-label="Send message"><Send size={18} /></button>
          </div>
          <p className="composer-note">Responses can include generated SQL. Verify important production decisions.</p>
        </footer>
      </main>
    </div>
  );
}
