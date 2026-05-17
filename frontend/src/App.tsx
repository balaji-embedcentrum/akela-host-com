import { useEffect, useState } from "react";
import { Route, Routes } from "react-router-dom";

/** Theme toggle — mirrors bbalaji-site (data-theme + localStorage). */
export function useTheme() {
  const [theme, setTheme] = useState<string>(
    () => document.documentElement.getAttribute("data-theme") || "light",
  );
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    try {
      localStorage.setItem("theme", theme);
    } catch {
      /* ignore */
    }
  }, [theme]);
  return { theme, toggle: () => setTheme((t) => (t === "dark" ? "light" : "dark")) };
}

function Shell({ children }: { children: React.ReactNode }) {
  const { theme, toggle } = useTheme();
  return (
    <>
      <nav>
        <a href="/" className="brand">
          <span className="brand-mark">A</span>
          <span>Akela Host</span>
        </a>
        <div className="nav-right">
          <a className="nav-link" href="/#pricing">
            Pricing
          </a>
          <button className="theme-toggle" onClick={toggle} aria-label="Toggle theme">
            {theme === "dark" ? "Light" : "Dark"}
          </button>
        </div>
      </nav>
      <main>{children}</main>
      <footer>
        <span>© {new Date().getFullYear()} Akela Host</span>
        <span>Rent Hermes agents · $4/mo</span>
      </footer>
    </>
  );
}

function LandingPlaceholder() {
  return (
    <header className="hero">
      <div className="eyebrow">
        <span className="dot" aria-hidden="true" />
        Scaffolding online
      </div>
      <h1>
        Rent <span className="accent">Hermes</span> agents.
      </h1>
      <p className="lead">
        Persistent, fully-owned AI agents for <strong>$4/month</strong>. Connect them to your
        own self-hosted Akela AI. Full UI ships in Epic 8.
      </p>
    </header>
  );
}

export function App() {
  return (
    <Shell>
      <Routes>
        <Route path="*" element={<LandingPlaceholder />} />
      </Routes>
    </Shell>
  );
}
