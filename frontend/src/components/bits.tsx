import { useState } from "react";

const OK = new Set(["deployed", "running"]);
const WARN = new Set(["pending", "paid", "stopped", "canceling", "recycling"]);

export function StatusBadge({ status }: { status: string }) {
  const cls = OK.has(status) ? "ok" : WARN.has(status) ? "warn" : "err";
  return <span className={`badge ${cls}`}>{status}</span>;
}

export function CopyField({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable */
    }
  };
  return (
    <div>
      <div className="cred-lbl lbl">{label}</div>
      <div className="cred">
        <code>{value}</code>
        <button className="btn btn-ghost btn-sm" onClick={copy}>
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
    </div>
  );
}
