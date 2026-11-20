import axios, {
  type AxiosError,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from "axios";
import type { NavigateFunction } from "react-router-dom";

export const api = axios.create({
  baseURL: "/api/v1",
});

// Attach the token to every request. Registered once at module load (not inside a React effect),
// so no request can ever be sent without it — e.g. a page's first query firing during a route change.
api.interceptors.request.use((config: InternalAxiosRequestConfig): InternalAxiosRequestConfig => {
  const token = localStorage.getItem("access_token");
  if (token && config.headers) {
    config.headers["Authorization"] = `Bearer ${token}`;
  }
  return config;
});

/** On 401 (expired/invalid token): clear the session and go to /login. Returns a cleanup function. */
export const setupInterceptors = (
  navigate: NavigateFunction,
  onUnauthorized?: () => void,
): (() => void) => {
  const responseInterceptor: number = api.interceptors.response.use(
    (response: AxiosResponse): AxiosResponse => response,
    (error: AxiosError): Promise<AxiosError> => {
      const isLoginRequest = error.config?.url?.includes("/login");

      if (error.response?.status === 401 && !isLoginRequest) {
        localStorage.removeItem("access_token");
        onUnauthorized?.();
        navigate("/login", { replace: true });
      }
      return Promise.reject(error);
    },
  );

  return () => {
    api.interceptors.response.eject(responseInterceptor);
  };
};
