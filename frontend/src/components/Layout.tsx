import { Link, useNavigate } from "react-router-dom";

import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useTheme } from "../lib/theme";

export function Layout({ children }: { children: React.ReactNode }) {
  const { theme, toggle } = useTheme();
  const { user, refresh } = useAuth();
  const nav = useNavigate();

  const logout = async () => {
    await api.logout();
    await refresh();
    nav("/");
  };

  return (
    <>
      <nav>
        <Link to="/" className="brand">
          <span className="brand-mark">A</span>
          <span>Akela Host</span>
        </Link>
        <div className="nav-right">
          <a className="nav-link" href="/#pricing">
            Pricing
          </a>
          {user ? (
            <>
              <Link className="nav-link" to="/dashboard">
                Dashboard
              </Link>
              {user.is_admin && (
                <Link className="nav-link" to="/admin">
                  Admin
                </Link>
              )}
              <button className="theme-toggle" onClick={logout}>
                Sign out
              </button>
            </>
          ) : (
            <a className="nav-link" href={api.loginUrl("mock")}>
              Sign in
            </a>
          )}
          <button className="theme-toggle" onClick={toggle} aria-label="Toggle theme">
            {theme === "dark" ? "Light" : "Dark"}
          </button>
        </div>
      </nav>
      <main>{children}</main>
      <footer>
        <span>© {new Date().getFullYear()} Akela Host · Rent Hermes agents</span>
        <span>$4/mo per agent · connect to your own Akela AI</span>
      </footer>
    </>
  );
}
