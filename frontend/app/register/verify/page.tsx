"use client";

import { Suspense, useCallback, useEffect, useRef, useState, type ClipboardEvent, type KeyboardEvent } from "react";
import { useSearchParams } from "next/navigation";
import { useAuth } from "../../providers";
import styles from "../../page.module.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function Brand() {
  return (
    <div className={styles.brand}>
      <span className={styles.mark} aria-hidden="true">L</span>
      <span>Local AI</span>
    </div>
  );
}

export default function VerifyRegistrationPage() {
  return (
    <Suspense fallback={<main className={styles.authStage}><section className={styles.loadingCard}>Loading verification…</section></main>}>
      <VerifyRegistrationForm />
    </Suspense>
  );
}

function VerifyRegistrationForm() {
  const { login } = useAuth();
  const searchParams = useSearchParams();
  const registrationId = searchParams.get("registration_id") ?? "";
  const email = searchParams.get("email") ?? "";
  const [digits, setDigits] = useState(["", "", "", ""]);
  const [resendIn, setResendIn] = useState(() => {
    const cooldown = Number(searchParams.get("resend_in"));
    return Number.isFinite(cooldown) && cooldown >= 0 ? cooldown : 60;
  });
  const [error, setError] = useState<string | null>(null);
  const [complete, setComplete] = useState(false);
  const [pending, setPending] = useState<"verify" | "resend" | "login" | null>(null);
  const inputs = useRef<Array<HTMLInputElement | null>>([]);

  useEffect(() => {
    if (resendIn <= 0) return;
    const timer = window.setTimeout(() => setResendIn((value) => Math.max(0, value - 1)), 1000);
    return () => window.clearTimeout(timer);
  }, [resendIn]);

  const continueToLogin = useCallback(async () => {
    setPending("login");
    setError(null);
    try {
      await login();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not open Keycloak sign-in.");
      setPending(null);
    }
  }, [login]);

  useEffect(() => {
    if (!complete) return;
    const timer = window.setTimeout(() => void continueToLogin(), 1800);
    return () => window.clearTimeout(timer);
  }, [complete, continueToLogin]);

  function changeDigit(index: number, rawValue: string) {
    const value = rawValue.replace(/\D/g, "").slice(-1);
    setDigits((previous) => {
      const next = [...previous];
      next[index] = value;
      return next;
    });
    if (value && index < 3) inputs.current[index + 1]?.focus();
    setError(null);
  }

  function onDigitKeyDown(index: number, event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Backspace" && !digits[index] && index > 0) {
      inputs.current[index - 1]?.focus();
    }
    if (event.key === "ArrowLeft" && index > 0) inputs.current[index - 1]?.focus();
    if (event.key === "ArrowRight" && index < 3) inputs.current[index + 1]?.focus();
  }

  function pasteCode(event: ClipboardEvent<HTMLDivElement>) {
    const pasted = event.clipboardData.getData("text").replace(/\D/g, "").slice(0, 4);
    if (!pasted) return;
    event.preventDefault();
    setDigits(Array.from({ length: 4 }, (_, index) => pasted[index] ?? ""));
    inputs.current[Math.min(pasted.length, 3)]?.focus();
    setError(null);
  }

  async function verify() {
    if (!registrationId) {
      setError("This registration link is missing or invalid. Please start again.");
      return;
    }
    if (digits.some((digit) => !digit)) {
      setError("Enter all four digits from the email.");
      inputs.current[digits.findIndex((digit) => !digit)]?.focus();
      return;
    }

    setError(null);
    setPending("verify");
    try {
      const response = await fetch(`${API_URL}/api/v1/auth/verify-otp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ registration_id: registrationId, otp: digits.join("") }),
      });
      const result = (await response.json()) as { detail?: string };
      if (!response.ok) throw new Error(result.detail ?? "The code could not be verified.");
      setComplete(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The code could not be verified.");
    } finally {
      setPending(null);
    }
  }

  async function resend() {
    if (!registrationId) {
      setError("This registration link is missing or invalid. Please start again.");
      return;
    }
    setError(null);
    setPending("resend");
    try {
      const response = await fetch(`${API_URL}/api/v1/auth/resend-otp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ registration_id: registrationId }),
      });
      const result = (await response.json()) as { detail?: string; resend_in_seconds?: number };
      if (!response.ok) {
        const retryAfter = Number(response.headers.get("Retry-After"));
        if (response.status === 429 && retryAfter > 0) setResendIn(retryAfter);
        throw new Error(result.detail ?? "A new code could not be sent.");
      }
      setDigits(["", "", "", ""]);
      setResendIn(result.resend_in_seconds ?? 60);
      inputs.current[0]?.focus();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "A new code could not be sent.");
    } finally {
      setPending(null);
    }
  }

  return (
    <main className={styles.authStage}>
      <section className={`${styles.loginCard} ${styles.registrationCard}`} aria-labelledby="verify-otp-title">
        <Brand />
        {complete ? (
          <div role="status" aria-live="polite">
            <p className={styles.eyebrow}>EMAIL VERIFIED</p>
            <h1 id="verify-otp-title">Your account is ready.</h1>
            <p className={styles.loginIntro}>Your email is verified. Opening Keycloak sign-in…</p>
            {error && <div className={styles.authError} role="alert">{error}</div>}
            <button className={styles.primaryAuthButton} type="button" disabled={pending === "login"} onClick={() => void continueToLogin()}>
              {pending === "login" ? "Opening sign in…" : "Continue to sign in"}
            </button>
          </div>
        ) : (
          <>
            <p className={styles.eyebrow}>EMAIL VERIFICATION</p>
            <h1 id="verify-otp-title">Enter your code.</h1>
            <p className={styles.loginIntro}>
              Enter the four-digit code sent to <strong>{email || "your email address"}</strong>. It expires five minutes after it was sent.
            </p>
            {error && <div className={styles.authError} role="alert">{error}</div>}
            {error && /expired|start again|no longer/i.test(error) && (
              <p className={styles.registrationFooter}>
                <a className={styles.verificationLink} href="/register">Start registration again</a>
              </p>
            )}
            <div className={styles.otpInputs} onPaste={pasteCode} aria-label="Four-digit verification code">
              {digits.map((digit, index) => (
                <input
                  key={index}
                  ref={(element) => { inputs.current[index] = element; }}
                  aria-label={`Verification digit ${index + 1}`}
                  autoComplete={index === 0 ? "one-time-code" : "off"}
                  className={styles.otpInput}
                  disabled={pending !== null}
                  inputMode="numeric"
                  maxLength={1}
                  pattern="[0-9]*"
                  type="text"
                  value={digit}
                  onChange={(event) => changeDigit(index, event.target.value)}
                  onKeyDown={(event) => onDigitKeyDown(index, event)}
                />
              ))}
            </div>
            <button className={styles.primaryAuthButton} type="button" disabled={pending !== null} onClick={() => void verify()}>
              {pending === "verify" ? "Verifying…" : "Verify email"}
            </button>
            <div className={styles.resendLine}>
              <span>{resendIn > 0 ? `Resend available in ${resendIn}s` : "Didn’t receive a code?"}</span>
              <button type="button" disabled={pending !== null || resendIn > 0} onClick={() => void resend()}>
                {pending === "resend" ? "Sending…" : "Resend code"}
              </button>
            </div>
            <p className={styles.localNote}>
              Local development email can be inspected in <a className={styles.verificationLink} href="http://localhost:8025" target="_blank" rel="noreferrer">Mailpit</a>.
            </p>
          </>
        )}
      </section>
    </main>
  );
}
