"use client";

import { useState } from "react";
import { useAuth } from "./providers";
import { Workspace } from "./workspace";
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
            Sign-in uses your local Keycloak service. Registration uses a four-digit email code.
          </p>
        </section>
      </main>
    );
  }

  return <Workspace />;
}
