"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import { useAuth } from "./providers";
import styles from "./workspace.module.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const ACCEPTED = ".pdf,.docx,.txt,.png,.jpg,.jpeg";
const MAX_FILE_BYTES = 25 * 1024 * 1024;

type Conversation = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  last_message?: string | null;
};
type Source = { index: number; document_id: string; filename: string; page?: number | null; chunk_index?: number | null };
type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  created_at?: string;
};
type DocumentItem = {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  status: "pending" | "processing" | "completed" | "failed";
  error_message?: string | null;
};

async function api<T>(path: string, token: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await fetch(`${API_URL}${path}`, { ...init, headers });
  if (!response.ok) {
    let message = `Request failed (${response.status}).`;
    try {
      const payload = await response.json();
      if (typeof payload.detail === "string") message = payload.detail;
    } catch { /* use the status fallback */ }
    throw new Error(message);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

function uploadWithProgress(form: FormData, token: string, onProgress: (value: number) => void) {
  return new Promise<{ documents: DocumentItem[] }>((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", `${API_URL}/api/v1/documents/upload`);
    request.setRequestHeader("Authorization", `Bearer ${token}`);
    request.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100));
    };
    request.onload = () => {
      let payload: { detail?: string; documents?: DocumentItem[] } = {};
      try { payload = JSON.parse(request.responseText); } catch { /* fallback below */ }
      if (request.status >= 200 && request.status < 300 && payload.documents) {
        resolve({ documents: payload.documents });
      } else {
        reject(new Error(payload.detail ?? `Upload failed (${request.status}).`));
      }
    };
    request.onerror = () => reject(new Error("The upload could not reach the local API."));
    request.onabort = () => reject(new Error("The upload was cancelled."));
    request.send(form);
  });
}

function formatBytes(bytes: number) {
  return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function Workspace() {
  const { username, getAccessToken, logout } = useAuth();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversation, setActiveConversation] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [selectedDocuments, setSelectedDocuments] = useState<Set<string>>(new Set());
  const [openConversationMenu, setOpenConversationMenu] = useState<string | null>(null);
  const [conversationToDelete, setConversationToDelete] = useState<Conversation | null>(null);
  const [deletingConversation, setDeletingConversation] = useState<string | null>(null);
  const [deleteConversationError, setDeleteConversationError] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [creating, setCreating] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [retryingDocument, setRetryingDocument] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retryMessage, setRetryMessage] = useState<{ text: string; id: string; documentIds: string[] } | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const chatEnd = useRef<HTMLDivElement>(null);

  const refreshDocuments = useCallback(async () => {
    const token = await getAccessToken();
    setDocuments(await api<DocumentItem[]>("/api/v1/documents", token));
  }, [getAccessToken]);

  const loadConversation = useCallback(async (id: string): Promise<boolean> => {
    setError(null);
    try {
      const token = await getAccessToken();
      const conversation = await api<Conversation & { messages: Message[] }>(`/api/v1/conversations/${id}`, token);
      setActiveConversation(id);
      setMessages(conversation.messages);
      setRetryMessage(null);
      return true;
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load this conversation.");
      return false;
    }
  }, [getAccessToken]);

  const createConversation = useCallback(async () => {
    setCreating(true);
    setError(null);
    try {
      const token = await getAccessToken();
      const conversation = await api<Conversation>("/api/v1/conversations", token, {
        method: "POST", body: JSON.stringify({ title: "New conversation" }),
      });
      setConversations((current) => [conversation, ...current]);
      setActiveConversation(conversation.id);
      setMessages([]);
      setRetryMessage(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not create a conversation.");
    } finally {
      setCreating(false);
    }
  }, [getAccessToken]);

  useEffect(() => {
    let active = true;
    async function initialize() {
      try {
        const token = await getAccessToken();
        const [history, library] = await Promise.all([
          api<Conversation[]>("/api/v1/conversations", token),
          api<DocumentItem[]>("/api/v1/documents", token),
        ]);
        if (!active) return;
        setConversations(history);
        setDocuments(library);
        if (history.length) {
          const conversation = await api<Conversation & { messages: Message[] }>(`/api/v1/conversations/${history[0].id}`, token);
          if (active) {
            setActiveConversation(history[0].id);
            setMessages(conversation.messages);
          }
        } else if (active) {
          const conversation = await api<Conversation>("/api/v1/conversations", token, {
            method: "POST", body: JSON.stringify({ title: "New conversation" }),
          });
          if (active) {
            setConversations([conversation]);
            setActiveConversation(conversation.id);
          }
        }
      } catch (caught) {
        if (active) setError(caught instanceof Error ? caught.message : "Could not load your workspace.");
      }
    }
    void initialize();
    const poll = window.setInterval(() => { void refreshDocuments().catch(() => undefined); }, 3000);
    return () => { active = false; window.clearInterval(poll); };
  }, [getAccessToken, refreshDocuments]);

  useEffect(() => { chatEnd.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, sending]);

  async function sendMessage(text: string, clientId = crypto.randomUUID(), documentIds = [...selectedDocuments]) {
    if (!activeConversation || !text.trim() || sending) return;
    setSending(true);
    setError(null);
    setRetryMessage({ text, id: clientId, documentIds });
    if (!messages.some((message) => message.id === clientId)) {
      setMessages((current) => [...current, { id: clientId, role: "user", content: text }]);
    }
    try {
      const token = await getAccessToken();
      const response = await api<Message>(`/api/v1/conversations/${activeConversation}/messages`, token, {
        method: "POST",
        body: JSON.stringify({ message: text, client_message_id: clientId, document_ids: documentIds }),
      });
      setMessages((current) => [...current, response]);
      const title = text.slice(0, 72).trim() || "New conversation";
      setConversations((current) => current.map((item) => item.id === activeConversation
        ? { ...item, title: item.title === "New conversation" ? title : item.title, last_message: text, updated_at: new Date().toISOString() } : item));
      setRetryMessage(null);
      setDraft("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The assistant could not answer. Try again.");
    } finally {
      setSending(false);
    }
  }

  async function uploadFiles(fileList: FileList | File[]) {
    const files = Array.from(fileList);
    if (!files.length) return;
    const allowed = new Set(["pdf", "docx", "txt", "png", "jpg", "jpeg"]);
    const invalid = files.find((file) => !allowed.has(file.name.split(".").pop()?.toLowerCase() ?? "") || file.size > MAX_FILE_BYTES || file.size === 0);
    if (invalid) {
      setError(`${invalid.name}: choose a non-empty PDF, DOCX, TXT, PNG, or JPG no larger than 25 MB.`);
      return;
    }
    setUploading(true);
    setUploadProgress(0);
    setError(null);
    try {
      const token = await getAccessToken();
      const form = new FormData();
      files.forEach((file) => form.append("files", file));
      await uploadWithProgress(form, token, setUploadProgress);
      await refreshDocuments();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Upload failed. Please retry.");
    } finally {
      setUploading(false);
      setUploadProgress(0);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  function onFilePicker(event: ChangeEvent<HTMLInputElement>) {
    if (event.target.files) void uploadFiles(event.target.files);
  }
  function onDrop(event: DragEvent<HTMLElement>) {
    event.preventDefault();
    event.stopPropagation();
    setDragging(false);
    void uploadFiles(event.dataTransfer.files);
  }
  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void sendMessage(draft.trim());
  }
  function onComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void sendMessage(draft.trim());
    }
  }
  function toggleDocument(id: string) {
    setSelectedDocuments((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }
  async function removeDocument(document: DocumentItem) {
    if (!window.confirm(`Delete “${document.filename}” and its indexed content?`)) return;
    try {
      const token = await getAccessToken();
      await api<void>(`/api/v1/documents/${document.id}`, token, { method: "DELETE" });
      setDocuments((current) => current.filter((item) => item.id !== document.id));
      setSelectedDocuments((current) => { const next = new Set(current); next.delete(document.id); return next; });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not delete the document.");
    }
  }
  async function retryDocument(document: DocumentItem) {
    setRetryingDocument(document.id);
    try {
      const token = await getAccessToken();
      const retried = await api<DocumentItem>(`/api/v1/documents/${document.id}/retry`, token, { method: "POST" });
      setDocuments((current) => current.map((item) => item.id === retried.id ? retried : item));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not retry document processing.");
    } finally {
      setRetryingDocument(null);
    }
  }

  async function renameConversation(conversation: Conversation) {
    setOpenConversationMenu(null);
    const proposed = window.prompt("Rename conversation", conversation.title);
    if (proposed === null) return;
    const title = proposed.trim();
    if (!title) {
      setError("Conversation titles cannot be blank.");
      return;
    }
    try {
      const token = await getAccessToken();
      const renamed = await api<Conversation>(`/api/v1/conversations/${conversation.id}`, token, {
        method: "PATCH",
        body: JSON.stringify({ title }),
      });
      setConversations((current) => current.map((item) => item.id === renamed.id
        ? { ...item, title: renamed.title, updated_at: renamed.updated_at } : item));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not rename the conversation.");
    }
  }

  async function deleteConversation(conversation: Conversation) {
    setDeletingConversation(conversation.id);
    setDeleteConversationError(null);
    try {
      const token = await getAccessToken();
      await api<void>(`/api/v1/conversations/${conversation.id}`, token, { method: "DELETE" });
      const remaining = conversations.filter((item) => item.id !== conversation.id);
      setConversations(remaining);
      setConversationToDelete(null);
      setOpenConversationMenu(null);
      setError(null);
      if (activeConversation === conversation.id) {
        setActiveConversation(null);
        setMessages([]);
        setRetryMessage(null);
        if (remaining[0]) {
          const loaded = await loadConversation(remaining[0].id);
          if (!loaded) await createConversation();
        } else {
          await createConversation();
        }
      }
    } catch (caught) {
      setDeleteConversationError(caught instanceof Error ? caught.message : "Could not delete the conversation. Please try again.");
    } finally {
      setDeletingConversation(null);
    }
  }

  return (
    <main className={styles.workspace} onDragEnter={(event) => { if (event.dataTransfer.types.includes("Files")) setDragging(true); }} onDragOver={(event) => event.preventDefault()} onDragLeave={(event) => { if (event.currentTarget === event.target) setDragging(false); }} onDrop={onDrop}>
      <aside className={styles.sidebar}>
        <div className={styles.brand}><span className={styles.brandMark}>L</span><span>Local AI</span></div>
        <button className={styles.newButton} onClick={() => void createConversation()} disabled={creating} type="button">＋ {creating ? "Creating…" : "New chat"}</button>
        <div className={styles.sectionLabel}>CONVERSATIONS</div>
        <div className={styles.conversationList}>
          {conversations.map((conversation) => (
            <div key={conversation.id} className={`${styles.conversationItem} ${activeConversation === conversation.id ? styles.activeConversation : ""}`}>
              <button type="button" className={styles.conversationOpen} onClick={() => { setOpenConversationMenu(null); void loadConversation(conversation.id); }}>
                <span>{conversation.title || "New conversation"}</span>
                {conversation.last_message && <small>{conversation.last_message}</small>}
              </button>
              <div className={styles.conversationActions}>
                <button
                  type="button"
                  className={styles.conversationMenuButton}
                  aria-label={`Actions for ${conversation.title || "New conversation"}`}
                  aria-haspopup="menu"
                  aria-expanded={openConversationMenu === conversation.id}
                  onClick={() => setOpenConversationMenu((current) => current === conversation.id ? null : conversation.id)}
                >···</button>
                {openConversationMenu === conversation.id && (
                  <div className={styles.conversationMenu} role="menu" onKeyDown={(event) => {
                    if (event.key === "Escape") setOpenConversationMenu(null);
                  }}>
                    <button type="button" role="menuitem" onClick={() => void renameConversation(conversation)}>Rename</button>
                    <button type="button" role="menuitem" onClick={() => { setOpenConversationMenu(null); setDeleteConversationError(null); setConversationToDelete(conversation); }}>Delete</button>
                  </div>
                )}
              </div>
            </div>
          ))}
          {!conversations.length && <p className={styles.muted}>Your chats will appear here.</p>}
        </div>
        <div className={styles.sidebarFooter}><span className={styles.avatar}>{username?.slice(0, 1).toUpperCase() ?? "U"}</span><span title={username ?? "Account"}>{username}</span><button type="button" onClick={() => void logout()}>Log out</button></div>
      </aside>

      <section className={styles.mainPane}>
        <header className={styles.header}><div><span className={styles.breadcrumb}>Workspace</span><span className={styles.separator}>/</span><strong>{conversations.find((item) => item.id === activeConversation)?.title ?? "New conversation"}</strong></div><span className={styles.localBadge}>● Local-first</span></header>
        <div className={styles.chat} aria-live="polite">
          {!messages.length && <div className={styles.emptyState}><span className={styles.sparkle}>✳</span><h1>What would you like to understand?</h1><p>Ask a question, or select documents and get answers grounded in their contents.</p></div>}
          {messages.map((message) => (
            <article key={message.id} className={`${styles.message} ${message.role === "user" ? styles.userMessage : styles.assistantMessage}`}>
              <div className={styles.messageRole}>{message.role === "user" ? "You" : "Local AI"}</div>
              <div className={styles.messageText}>{message.content}</div>
              {message.sources?.length ? <div className={styles.sources}>Sources: {message.sources.map((source) => <span key={`${source.document_id}-${source.index}`}>[{source.index}] {source.filename}{source.page ? ` · p. ${source.page}` : ""}{source.chunk_index != null ? ` · chunk ${source.chunk_index + 1}` : ""}</span>)}</div> : null}
            </article>
          ))}
          {sending && <div className={styles.thinking} role="status"><span className={styles.spinner} /> Thinking with your local model…</div>}
          <div ref={chatEnd} />
        </div>
        {error && <div className={styles.errorBanner} role="alert"><span>{error}</span>{retryMessage && !sending && <button type="button" onClick={() => void sendMessage(retryMessage.text, retryMessage.id, retryMessage.documentIds)}>Retry response</button>}<button aria-label="Dismiss error" onClick={() => setError(null)}>×</button></div>}
        <div className={styles.composerWrap}>
          {selectedDocuments.size > 0 && <div className={styles.selectionNote}>Using {selectedDocuments.size} selected {selectedDocuments.size === 1 ? "document" : "documents"}</div>}
          <form className={styles.composer} onSubmit={onSubmit}>
            <button type="button" className={styles.attachButton} aria-label="Attach documents" title="Upload documents" onClick={() => fileInput.current?.click()} disabled={uploading}>＋</button>
            <input ref={fileInput} type="file" accept={ACCEPTED} multiple className={styles.hiddenInput} onChange={onFilePicker} />
            <textarea value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={onComposerKeyDown} placeholder="Ask a question about your documents…" maxLength={8000} rows={1} aria-label="Message" />
            <button type="submit" className={styles.sendButton} disabled={sending || !draft.trim()} aria-label="Send message">↑</button>
          </form>
          <p className={styles.composerHint}>Enter to send · Shift+Enter for a new line · Answers run locally</p>
        </div>
      </section>

      <aside className={styles.documentsPane} aria-label="Document library">
        <div className={styles.documentHeader}><div><span className={styles.sectionLabel}>YOUR LIBRARY</span><h2>Documents</h2></div><button type="button" aria-label="Upload documents" title="Upload documents" onClick={() => fileInput.current?.click()}>＋</button></div>
        <button type="button" className={styles.dropZone} onClick={() => fileInput.current?.click()} onDragOver={(event) => event.preventDefault()} onDrop={onDrop} disabled={uploading}>
          <span>↥</span><strong>{uploading ? `Uploading ${uploadProgress}%` : "Add documents"}</strong><small>PDF, DOCX, TXT, PNG, JPG · up to 25 MB</small>
          {uploading && <span className={styles.progressTrack}><span style={{ width: `${uploadProgress}%` }} /></span>}
        </button>
        <div className={styles.documentList}>
          {documents.map((document) => (
            <div className={styles.documentItem} key={document.id}>
              <label className={styles.documentSelect} title="Use this document for answers">
                <input type="checkbox" checked={selectedDocuments.has(document.id)} disabled={document.status !== "completed"} onChange={() => toggleDocument(document.id)} />
                <span className={styles.fileIcon}>{document.filename.split(".").pop()?.toUpperCase()}</span>
                <span className={styles.fileInfo}><strong title={document.filename}>{document.filename}</strong><small>{formatBytes(document.size_bytes)} · {document.status === "completed" ? "Ready to search" : document.status === "failed" ? "Processing failed" : document.status === "processing" ? "Extracting and indexing…" : "Waiting to process…"}</small></span>
              </label>
              <button type="button" className={styles.deleteButton} aria-label={`Delete ${document.filename}`} onClick={() => void removeDocument(document)}>×</button>
              {document.status === "failed" && document.error_message && <p className={styles.documentError}>{document.error_message}</p>}
              {document.status === "failed" && <button type="button" className={styles.retryDocument} disabled={retryingDocument === document.id} onClick={() => void retryDocument(document)}>{retryingDocument === document.id ? "Retrying…" : "Retry indexing"}</button>}
            </div>
          ))}
          {!documents.length && <p className={styles.muted}>Upload a file to start building your private library.</p>}
        </div>
        <p className={styles.privacyNote}>Files and embeddings stay in your local Docker volumes.</p>
      </aside>
      {dragging && <div className={styles.dragOverlay} onDragLeave={() => setDragging(false)}><div>Drop files to add them to your library</div></div>}
      {conversationToDelete && (
        <div className={styles.dialogBackdrop}>
          <section
            className={styles.deleteDialog}
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="delete-conversation-title"
            aria-describedby="delete-conversation-description"
            onKeyDown={(event) => {
              if (event.key === "Escape" && deletingConversation !== conversationToDelete.id) {
                setConversationToDelete(null);
                setDeleteConversationError(null);
              }
            }}
          >
            <h2 id="delete-conversation-title">Delete conversation?</h2>
            <p id="delete-conversation-description">
              Delete “{conversationToDelete.title || "New conversation"}” and its messages? Your documents and indexed content will remain.
            </p>
            {deleteConversationError && <p className={styles.dialogError} role="alert">{deleteConversationError}</p>}
            <div className={styles.dialogActions}>
              <button type="button" onClick={() => { setConversationToDelete(null); setDeleteConversationError(null); }} disabled={deletingConversation === conversationToDelete.id}>Cancel</button>
              <button type="button" className={styles.confirmDelete} onClick={() => void deleteConversation(conversationToDelete)} disabled={deletingConversation === conversationToDelete.id}>
                {deletingConversation === conversationToDelete.id ? "Deleting…" : "Delete"}
              </button>
            </div>
          </section>
        </div>
      )}
    </main>
  );
}
