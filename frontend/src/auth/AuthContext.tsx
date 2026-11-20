/* eslint-disable react-refresh/only-export-components -- small helpers live next to the provider */
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import * as authApi from "../api/auth";
import type { LoginRequest, RegisterRequest, UserOut } from "../api/types";

interface AuthState {
  user: UserOut | null;
  loading: boolean;
  login: (body: LoginRequest) => Promise<void>;
  register: (body: RegisterRequest) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserOut | null>(null);
  // If a token is stored we wait for /auth/me before rendering protected pages.
  const [loading, setLoading] = useState(authApi.isAuthenticated());

  useEffect(() => {
    if (!authApi.isAuthenticated()) return;
    authApi
      .getCurrentUser()
      .then(setUser)
      .catch(() => authApi.logout())
      .finally(() => setLoading(false));
  }, []);

  const value: AuthState = {
    user,
    loading,
    login: async (body) => setUser(await authApi.login(body)),
    register: async (body) => setUser(await authApi.register(body)),
    logout: () => {
      authApi.logout();
      setUser(null);
    },
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

export const isStaff = (user: UserOut | null) => user?.role === "teacher" || user?.role === "admin";
export const isAdmin = (user: UserOut | null) => user?.role === "admin";
