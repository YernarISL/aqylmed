import { api } from "./client";
import type { UserOut, TokenOut, RegisterRequest, LoginRequest } from "./types";

const TOKEN_KEY = "access_token";

const saveToken = (data: TokenOut): UserOut => {
    localStorage.setItem(TOKEN_KEY, data.access_token);
    return data.user;
};

/** Creates the account; the backend returns a token + the new user, so we're logged in immediately. */
export const register = async (body: RegisterRequest): Promise<UserOut> => {
    const response = await api.post<TokenOut>("/auth/register", body);
    return saveToken(response.data);
};

export const login = async (body: LoginRequest): Promise<UserOut> => {
    const response = await api.post<TokenOut>("/auth/login", body);
    return saveToken(response.data);
};

export const logout = (): void => {
    localStorage.removeItem(TOKEN_KEY);
};

/** Restores the user on page reload (token comes from localStorage via the interceptor). */
export const getCurrentUser = async (): Promise<UserOut> => {
    const response = await api.get<UserOut>("/auth/me");
    return response.data;
};

export const isAuthenticated = (): boolean => localStorage.getItem(TOKEN_KEY) !== null;
