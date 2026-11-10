"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import styles from "../page.module.css";

type RegistrationResponse = {
  registration_id: string;
  email: string;
  expires_in_seconds: number;
  resend_in_seconds: number;
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function Brand() {
  return (
    <div className={styles.brand}>
      <span className={styles.mark} aria-hidden="true">L</span>
      <span>Local AI</span>
    </div>
  );
}

export default function RegisterPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (password !== confirmPassword) {
      setError("The passwords do not match.");
      return;
    }

    setPending(true);
    try {
      const response = await fetch(`${API_URL}/api/v1/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username,
          email,
          first_name: firstName,
          last_name: lastName,
          password,
          confirm_password: confirmPassword,
        }),
      });
      const result = (await response.json()) as RegistrationResponse | { detail?: string };
      if (!response.ok || !("registration_id" in result)) {
        throw new Error("detail" in result ? result.detail : undefined);
      }
      setPassword("");
      setConfirmPassword("");
      const query = new URLSearchParams({
        registration_id: result.registration_id,
        email: result.email,
        resend_in: String(result.resend_in_seconds),
      });
      router.push(`/register/verify?${query.toString()}`);
    } catch (caught) {
      setError(
        caught instanceof Error && caught.message
          ? caught.message
          : "We could not start registration. Check your details and try again.",
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <main className={styles.authStage}>
      <section className={`${styles.loginCard} ${styles.registrationCard}`} aria-labelledby="register-title">
        <Brand />
        <p className={styles.eyebrow}>CREATE YOUR PRIVATE WORKSPACE</p>
        <h1 id="register-title">Create an account.</h1>
        <p className={styles.loginIntro}>We’ll email you a four-digit code to verify your address.</p>

        {error && <div className={styles.authError} role="alert">{error}</div>}
        <form className={styles.registrationForm} onSubmit={(event) => void submit(event)}>
          <label className={styles.formField}>
            <span>Username</span>
            <input
              autoComplete="username"
              className={styles.formInput}
              maxLength={64}
              minLength={3}
              pattern="[A-Za-z0-9._-]+"
              required
              value={username}
              onChange={(event) => setUsername(event.target.value)}
            />
          </label>
          <label className={styles.formField}>
            <span>Email</span>
            <input
              autoComplete="email"
              className={styles.formInput}
              maxLength={254}
              required
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </label>
          <div className={styles.formPair}>
            <label className={styles.formField}>
              <span>First name</span>
              <input
                autoComplete="given-name"
                className={styles.formInput}
                maxLength={100}
                required
                value={firstName}
                onChange={(event) => setFirstName(event.target.value)}
              />
            </label>
            <label className={styles.formField}>
              <span>Last name</span>
              <input
                autoComplete="family-name"
                className={styles.formInput}
                maxLength={100}
                required
                value={lastName}
                onChange={(event) => setLastName(event.target.value)}
              />
            </label>
          </div>
          <label className={styles.formField}>
            <span>Password</span>
            <input
              autoComplete="new-password"
              className={styles.formInput}
              maxLength={128}
              minLength={12}
              required
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
            <small>Use at least 12 characters.</small>
          </label>
          <label className={styles.formField}>
            <span>Confirm password</span>
            <input
              autoComplete="new-password"
              className={styles.formInput}
              maxLength={128}
              minLength={12}
              required
              type="password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
            />
          </label>
          <button className={styles.primaryAuthButton} type="submit" disabled={pending}>
            {pending ? "Sending verification code…" : "Register"}
          </button>
        </form>
        <p className={styles.registrationFooter}>
          Already registered? <button type="button" onClick={() => router.push("/")}>Sign in</button>
        </p>
      </section>
    </main>
  );
}
