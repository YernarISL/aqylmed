import axios, {
  type AxiosError,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from "axios";
import type { NavigateFunction } from "react-router-dom";

export const api = axios.create({
  baseURL: "/api/v1",
});

export const setupInterceptors = (navigate: NavigateFunction): (() => void) => {
  const requestInterceptor: number = api.interceptors.request.use(
    (config: InternalAxiosRequestConfig): InternalAxiosRequestConfig => {
      const token = localStorage.getItem("access_token");
      if (token && config.headers) {
        config.headers["Authorization"] = `Bearer ${token}`;
      }
      return config;
    },
    (error: AxiosError): Promise<AxiosError> => Promise.reject(error),
  );

  const responseInterceptor: number = api.interceptors.response.use(
    (response: AxiosResponse): AxiosResponse => response,
    (error: AxiosError): Promise<AxiosError> => {
      const isLoginRequest = error.config?.url?.includes("/login");

      if (error.response?.status === 401 && !isLoginRequest) {
        localStorage.removeItem("access_token");
        navigate("/login", { replace: true });
      }
      return Promise.reject(error);
    },
  );

  return () => {
    api.interceptors.request.eject(requestInterceptor);
    api.interceptors.response.eject(responseInterceptor);
  };
};
