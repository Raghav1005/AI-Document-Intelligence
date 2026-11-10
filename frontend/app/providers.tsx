"use client";

import type Keycloak from "keycloak-js";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type AuthStatus =
  | "loading"
  | "authenticated"
  | "unverified"
  | "anonymous"
  | "error";

type AuthSnapshot = {
  status: AuthStatus;
  username: string | null;
  email: string | null;
  error: string | null;
};

type AuthContextValue = AuthSnapshot & {
  login: () => Promise<void>;
  register: () => Promise<void>;
  logout: () => Promise<void>;
  getAccessToken: (minimumValiditySeconds?: number) => Promise<string>;
  retryInitialization: () => Promise<void>;
};

type AuthConfig = { url: string; realm: string; clientId: string };
type AuthListener = (snapshot: AuthSnapshot) => void;

const INITIAL_SNAPSHOT: AuthSnapshot = {
  status: "loading",
  username: null,
  email: null,
  error: null,
};

const LOGOUT_REDIRECT_URI = "http://localhost:3000";

const AuthContext = createContext<AuthContextValue | null>(null);
const listeners = new Set<AuthListener>();

// Module-level state is shared by React Strict Mode's setup/cleanup replay.
let keycloakInstance: Keycloak | null = null;
let instanceCreation: Promise<Keycloak> | null = null;
let initialization: Promise<boolean> | null = null;
let activeConfig: AuthConfig | null = null;
let currentSnapshot = INITIAL_SNAPSHOT;
let refreshTimer: number | undefined;

function publish(snapshot: AuthSnapshot) {
  currentSnapshot = snapshot;
  listeners.forEach((listener) => listener(snapshot));
}

function snapshotFromKeycloak(
  keycloak: Keycloak,
  status: AuthStatus,
  error: string | null = null,
): AuthSnapshot {
  const parsed = keycloak.tokenParsed;
  const username =
    (typeof parsed?.preferred_username === "string" && parsed.preferred_username) ||
    (typeof parsed?.email === "string" && parsed.email) ||
    null;
  const email = typeof parsed?.email === "string" ? parsed.email : null;

  return { status, username, email, error };
}

function authenticatedSnapshot(keycloak: Keycloak): AuthSnapshot {
  return snapshotFromKeycloak(
    keycloak,
    keycloak.tokenParsed?.email_verified === true ? "authenticated" : "unverified",
  );
}

function cancelRefreshTimer() {
  if (refreshTimer !== undefined && typeof window !== "undefined") {
    window.clearTimeout(refreshTimer);
    refreshTimer = undefined;
  }
}

function scheduleRefresh(keycloak: Keycloak) {
  cancelRefreshTimer();
  const expiresAt = keycloak.tokenParsed?.exp;
  if (!expiresAt || typeof window === "undefined") return;

  const refreshInMs = Math.max(expiresAt * 1000 - Date.now() - 60_000, 5_000);
  refreshTimer = window.setTimeout(() => {
    void refreshAccessToken(keycloak, 30).catch(() => undefined);
  }, refreshInMs);
}

async function refreshAccessToken(
  keycloak: Keycloak,
  minimumValiditySeconds: number,
): Promise<string> {
  if (!keycloak.authenticated || !keycloak.refreshToken) {
    throw new Error("Your sign-in session has expired. Please sign in again.");
  }

  try {
    await keycloak.updateToken(minimumValiditySeconds);
    if (!keycloak.token) throw new Error("Keycloak returned no access token.");
    publish(authenticatedSnapshot(keycloak));
    scheduleRefresh(keycloak);
    return keycloak.token;
  } catch {
    keycloak.clearToken();
    cancelRefreshTimer();
    publish({
      status: "error",
      username: null,
      email: null,
      error: "Your session could not be refreshed. Please sign in again.",
    });
    throw new Error("Your session could not be refreshed. Please sign in again.");
  }
}

function assertSameConfig(config: AuthConfig) {
  if (
    activeConfig &&
    (activeConfig.url !== config.url ||
      activeConfig.realm !== config.realm ||
      activeConfig.clientId !== config.clientId)
  ) {
    throw new Error("Keycloak configuration changed after initialization.");
  }
}

async function initializeKeycloak(config: AuthConfig): Promise<boolean> {
  if (typeof window === "undefined") {
    throw new Error("Keycloak can only be initialized in a browser.");
  }

  assertSameConfig(config);

  if (!instanceCreation) {
    instanceCreation = import("keycloak-js")
      .then(({ default: KeycloakConstructor }) => {
        if (!keycloakInstance) {
          keycloakInstance = new KeycloakConstructor(config);
          activeConfig = config;
        }
        return keycloakInstance;
      })
      .catch((error: unknown) => {
        instanceCreation = null;
        throw error;
      });
  }

  await instanceCreation;
  assertSameConfig(config);

  const keycloak = keycloakInstance;
  if (!keycloak) throw new Error("Keycloak instance creation failed.");

  if (!initialization) {
    keycloak.onAuthSuccess = () => {
      publish(authenticatedSnapshot(keycloak));
      scheduleRefresh(keycloak);
    };
    keycloak.onAuthRefreshSuccess = () => {
      publish(authenticatedSnapshot(keycloak));
      scheduleRefresh(keycloak);
    };
    keycloak.onAuthRefreshError = () => {
      keycloak.clearToken();
      cancelRefreshTimer();
      publish({
        status: "error",
        username: null,
        email: null,
        error: "Your session could not be refreshed. Please sign in again.",
      });
    };
    keycloak.onAuthLogout = () => {
      cancelRefreshTimer();
      publish({ status: "anonymous", username: null, email: null, error: null });
    };
    keycloak.onTokenExpired = () => {
      void refreshAccessToken(keycloak, 30).catch(() => undefined);
    };
    initialization = keycloak
      .init({
        onLoad: "check-sso",
        pkceMethod: "S256",
        checkLoginIframe: false,
      })
      .then((authenticated) => {
        publish(
          authenticated
            ? authenticatedSnapshot(keycloak)
            : { status: "anonymous", username: null, email: null, error: null },
        );
        if (authenticated) scheduleRefresh(keycloak);
        return authenticated;
      })
      .catch((error: unknown) => {
        initialization = null;
        instanceCreation = null;
        keycloakInstance = null;
        activeConfig = null;
        publish({
          status: "error",
          username: null,
          email: null,
          error:
            error instanceof Error
              ? `Could not connect to Keycloak: ${error.message}`
              : "Could not connect to Keycloak.",
        });
        throw error;
      });
  }

  return initialization;
}

function subscribe(listener: AuthListener) {
  listeners.add(listener);
  listener(currentSnapshot);
  return () => {
    listeners.delete(listener);
  };
}

type AuthProviderProps = {
  children: ReactNode;
  url: string;
  realm: string;
  clientId: string;
};

export function AuthProvider({
  children,
  url,
  realm,
  clientId,
}: AuthProviderProps) {
  const [snapshot, setSnapshot] = useState<AuthSnapshot>(currentSnapshot);
  const config = useMemo(() => ({ url, realm, clientId }), [url, realm, clientId]);

  useEffect(() => {
    const unsubscribe = subscribe(setSnapshot);
    void initializeKeycloak(config).catch(() => undefined);
    return unsubscribe;
  }, [config]);

  const login = useCallback(async () => {
    await initializeKeycloak(config);
    if (!keycloakInstance) throw new Error("Keycloak is not initialized.");
    await keycloakInstance.login({ redirectUri: window.location.origin });
  }, [config]);

  const register = useCallback(async () => {
    await initializeKeycloak(config);
    if (!keycloakInstance) throw new Error("Keycloak is not initialized.");
    await keycloakInstance.register({ redirectUri: window.location.origin });
  }, [config]);

  const logout = useCallback(async () => {
    if (!keycloakInstance) throw new Error("Keycloak is not initialized.");
    cancelRefreshTimer();
    const keycloak = keycloakInstance;
    try {
      const logoutRequest = keycloak.logout({ redirectUri: LOGOUT_REDIRECT_URI });
      publish({ status: "anonymous", username: null, email: null, error: null });
      await logoutRequest;
    } catch (error) {
      keycloak.clearToken();
      publish({
        status: "anonymous",
        username: null,
        email: null,
        error: "You have been signed out, but Keycloak could not be reached.",
      });
      throw error;
    }
  }, []);

  const getAccessToken = useCallback(
    async (minimumValiditySeconds = 30) => {
      if (!keycloakInstance || !initialization) {
        throw new Error("Authentication has not finished initializing.");
      }
      await initialization;
      const accessToken = await refreshAccessToken(keycloakInstance, minimumValiditySeconds);
      if (keycloakInstance.tokenParsed?.email_verified !== true) {
        publish(authenticatedSnapshot(keycloakInstance));
        throw new Error("Verify your email before using protected workspace features.");
      }
      return accessToken;
    },
    [],
  );

  const retryInitialization = useCallback(async () => {
    if (initialization) return;
    publish(INITIAL_SNAPSHOT);
    await initializeKeycloak(config);
  }, [config]);

  const value = useMemo<AuthContextValue>(
    () => ({
      ...snapshot,
      login,
      register,
      logout,
      getAccessToken,
      retryInitialization,
    }),
    [snapshot, login, register, logout, getAccessToken, retryInitialization],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
