import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { errorMessage } from "../api/errors";
import { useAuth } from "../auth/AuthContext";
import ui from "../components/ui.module.css";
import styles from "./AuthPage.module.css";

export default function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/" replace />;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login({ email, password });
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
        <h1>Sign in</h1>
        <p className={ui.muted}>Clinical case simulator and textbook assistant.</p>
        <form className={styles.form} onSubmit={onSubmit}>
          <label>
            Email
            <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
          <label>
            Password
            <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} />
          </label>
          {error && <div className={ui.error}>{error}</div>}
          <button disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
        </form>
        <div className={styles.footer}>
          No account? <Link to="/register">Register</Link>
        </div>
      </div>
    </div>
  );
}
