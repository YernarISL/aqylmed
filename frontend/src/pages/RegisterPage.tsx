import { useState, type ChangeEvent, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { errorMessage } from "../api/errors";
import type { RegisterRequest } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import ui from "../components/ui.module.css";
import styles from "./AuthPage.module.css";

export default function RegisterPage() {
  const { user, register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState<RegisterRequest>({
    email: "",
    password: "",
    first_name: "",
    last_name: "",
    university: "",
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/" replace />;

  const set = (key: keyof RegisterRequest) => (e: ChangeEvent<HTMLInputElement>) =>
    setForm({ ...form, [key]: e.target.value });

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await register(form);
      navigate("/");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={styles.wrap}>
      <div className={`${ui.card} ${styles.box}`}>
        <div className={styles.brand}>AQYLMED</div>
        <h1>Create a student account</h1>
        <form className={styles.form} onSubmit={onSubmit}>
          <div className={styles.two}>
            <label>
              First name
              <input required value={form.first_name} onChange={set("first_name")} />
            </label>
            <label>
              Last name
              <input value={form.last_name} onChange={set("last_name")} />
            </label>
          </div>
          <label>
            University
            <input value={form.university} onChange={set("university")} />
          </label>
          <label>
            Email
            <input type="email" required value={form.email} onChange={set("email")} />
          </label>
          <label>
            Password (min. 8 characters)
            <input type="password" required minLength={8} value={form.password} onChange={set("password")} />
          </label>
          {error && <div className={ui.error}>{error}</div>}
          <button disabled={busy}>{busy ? "Creating…" : "Create account"}</button>
        </form>
        <div className={styles.footer}>
          Already registered? <Link to="/login">Sign in</Link>
        </div>
      </div>
    </div>
  );
}
