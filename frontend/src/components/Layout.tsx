import { useQueryClient } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { isAdmin, isStaff, useAuth } from "../auth/AuthContext";
import styles from "./Layout.module.css";
import ui from "./ui.module.css";

export default function Layout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const queryClient = useQueryClient();

  const link = ({ isActive }: { isActive: boolean }) => (isActive ? `${styles.link} ${styles.active}` : styles.link);

  const onLogout = () => {
    logout();
    queryClient.clear();
  };

  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <div className={styles.inner}>
          <span className={styles.brand}>AQYLMED</span>
          <nav className={styles.nav}>
            <NavLink to="/" end className={link}>Cases</NavLink>
            <NavLink to="/history" className={link}>History</NavLink>
            <NavLink to="/chat" className={link}>Textbook chat</NavLink>
            {isStaff(user) && (
              <>
                <span className={styles.divider} />
                <NavLink to="/admin/cases" className={link}>Case templates</NavLink>
                <NavLink to="/admin/chat-logs" className={link}>Chat logs</NavLink>
              </>
            )}
            {isAdmin(user) && <NavLink to="/admin/textbooks" className={link}>Textbooks</NavLink>}
          </nav>
          <div className={styles.user}>
            <span>
              {user?.first_name} {user?.last_name}
            </span>
            <span className={ui.badge}>{user?.role}</span>
            <button className={`${ui.ghost} ${ui.small}`} onClick={onLogout}>
              Log out
            </button>
          </div>
        </div>
      </header>
      <main className={styles.main}>{children}</main>
    </div>
  );
}
