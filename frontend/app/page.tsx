"use client";

import { useState } from "react";
import { useAuth } from "./providers";
import styles from "./page.module.css";

function Brand() {
  return (
    <div className={styles.brand}>
      <span className={styles.mark} aria-hidden="true">
        L
      </span>
      <span>Local AI</span>
    </div>
  );
}

export default function HomePage() {
  const {
    status,
    username,
    email,
    error,
    login,
    register,
    logout,
    retryInitialization,
  } = useAuth();
  const [actionError, setActionError] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<
    "login" | "register" | "logout" | "retry" | null
  >(null);

  async function runAction(
    name: "login" | "register" | "logout" | "retry",
    action: () => Promise<void>,
  ) {
    setActionError(null);
    setPendingAction(name);
    try {
      await action();
    } catch (caught) {
      setActionError(
        caught instanceof Error
          ? caught.message
          : "The request could not be completed.",
      );
    } finally {
      setPendingAction(null);
    }
  }

  if (status === "loading") {
    return (
      <main className={styles.authStage}>
        <div className={styles.loadingCard} role="status" aria-live="polite">
          <Brand />
          <span className={styles.spinner} aria-hidden="true" />
          <h1>Connecting to your local identity service</h1>
          <p>Checking your sign-in session…</p>
        </div>
      </main>
    );
  }

  if (status === "unverified") {
    return (
      <main className={styles.authStage}>
        <section className={styles.loginCard} aria-labelledby="verify-title">
          <Brand />
          <div className={styles.loginAccent} aria-hidden="true">✉</div>
          <p className={styles.eyebrow}>ONE MORE STEP</p>
          <h1 id="verify-title">Verify your email.</h1>
          <p className={styles.loginIntro}>
            Verify your email address before opening your protected workspace.
            {email ? <> We sent a verification link to <strong>{email}</strong>.</> : " Check your inbox for a verification link."}
          </p>
          {actionError && <div className={styles.authError} role="alert">{actionError}</div>}
          <div className={styles.authActions}>
            <button
              className={styles.primaryAuthButton}
              type="button"
              disabled={pendingAction !== null}
              onClick={() => void runAction("logout", logout)}
            >
              {pendingAction === "logout" ? "Returning to sign in…" : "I've verified — return to sign in"}
            </button>
          </div>
          <p className={styles.localNote}>
            In this local setup, outgoing verification messages are captured by Mailpit at{" "}
            <a href="http://localhost:8025" target="_blank" rel="noreferrer">localhost:8025</a>.
          </p>
        </section>
      </main>
    );
  }

  if (status === "anonymous" || status === "error") {
    return (
      <main className={styles.authStage}>
        <section className={styles.loginCard} aria-labelledby="welcome-title">
          <Brand />
          <div className={styles.loginAccent} aria-hidden="true">✳</div>
          <p className={styles.eyebrow}>YOUR PRIVATE KNOWLEDGE SPACE</p>
          <h1 id="welcome-title">Welcome back.</h1>
          <p className={styles.loginIntro}>
            Sign in to explore your documents with AI that runs on your own computer.
          </p>

          {(error || actionError) && (
            <div className={styles.authError} role="alert">
              {actionError ?? error}
            </div>
          )}

          <div className={styles.authActions}>
            <button
              className={styles.primaryAuthButton}
              type="button"
              disabled={pendingAction !== null}
              onClick={() => void runAction("login", login)}
            >
              {pendingAction === "login" ? "Opening sign in…" : "Sign in"}
            </button>
            <button
              className={styles.secondaryAuthButton}
              type="button"
              disabled={pendingAction !== null}
              onClick={() => void runAction("register", register)}
            >
              {pendingAction === "register" ? "Opening registration…" : "Create account"}
            </button>
            {status === "error" && (
              <button
                className={styles.textAuthButton}
                type="button"
                disabled={pendingAction !== null}
                onClick={() => void runAction("retry", retryInitialization)}
              >
                {pendingAction === "retry" ? "Retrying…" : "Retry connection"}
              </button>
            )}
          </div>
          <p className={styles.localNote}>
            Authentication is handled by your local Keycloak service. Credentials are never entered in this app.
          </p>
        </section>
      </main>
    );
  }

  return (
    <main className={styles.frame}>
      <aside className={styles.sidebar} aria-label="Workspace navigation">
        <Brand />
        <button className={styles.newChat} type="button" disabled>
          <span aria-hidden="true">＋</span> New chat
        </button>
        <div className={styles.sidebarLabel}>WORKSPACE</div>
        <div className={styles.navItem}>⌕ <span>Search</span></div>
        <div className={styles.navItem}>▤ <span>Documents</span></div>
        <div className={styles.sidebarBottom}>
          <span className={styles.avatar}>{username?.slice(0, 1).toUpperCase() ?? "U"}</span>
          <span className={styles.username} title={username ?? "Signed in"}>{username ?? "Signed in"}</span>
        </div>
      </aside>

      <section className={styles.main}>
        <header className={styles.topbar}>
          <span>Workspace <span className={styles.slash}>/</span> New chat</span>
          <div className={styles.topbarRight}>
            <span className={styles.userLabel}>{username}</span>
            <span className={styles.localBadge}><span /> Local-first</span>
            <button
              className={styles.logoutButton}
              type="button"
              disabled={pendingAction !== null}
              onClick={() => void runAction("logout", logout)}
            >
              {pendingAction === "logout" ? "Signing out…" : "Logout"}
            </button>
          </div>
        </header>

        <div className={styles.content}>
          <div className={styles.eyebrow}>YOUR PRIVATE KNOWLEDGE SPACE</div>
          <h1>What would you like to understand?</h1>
          <p className={styles.intro}>Add your documents and ask questions. Your files and conversations stay on this computer.</p>

          <div className={styles.cards}>
            <article className={styles.card}>
              <span className={styles.cardIcon}>↥</span>
              <h2>Bring in your documents</h2>
              <p>PDF, Word, text, CSV, and Markdown support is coming with document ingestion.</p>
              <span className={styles.cardFoot}>DOCUMENT LIBRARY <span>01</span></span>
            </article>
            <article className={styles.card}>
              <span className={styles.cardIcon}>✳</span>
              <h2>Explore with local AI</h2>
              <p>Questions will be answered using your selected files and a model running locally.</p>
              <span className={styles.cardFoot}>PRIVATE BY DESIGN <span>02</span></span>
            </article>
            <article className={styles.card}>
              <span className={styles.cardIcon}>文</span>
              <h2>Work in your language</h2>
              <p>English and Hindi input and responses are planned for the first release.</p>
              <span className={styles.cardFoot}>ENGLISH · हिन्दी <span>03</span></span>
            </article>
          </div>

          <div className={styles.notice}>
            <span className={styles.noticeIcon}>◷</span>
            <div><strong>Workspace setup is underway</strong><span>Authentication, document indexing, and chat are added in separate, testable features.</span></div>
          </div>
          <div className={styles.composer} aria-disabled="true">
            <span>Chat will be available after local model setup</span>
            <button type="button" disabled aria-label="Send message">↑</button>
          </div>
          {actionError && <p className={styles.inlineError} role="alert">{actionError}</p>}
          <p className={styles.caption}>Your documents will be processed and searched on this device.</p>
        </div>
      </section>
    </main>
  );
}
