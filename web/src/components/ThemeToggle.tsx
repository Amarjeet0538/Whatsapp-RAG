import { useEffect, useState } from "react";
import { safeStorage } from "../storage";

type Theme = "light" | "dark" | null; // null follows the system setting

const LABEL: Record<string, string> = { system: "System", light: "Light", dark: "Dark" };
const NEXT: Record<string, Theme> = { system: "light", light: "dark", dark: null };

function readTheme(): Theme {
  const v = safeStorage("local")?.getItem("theme");
  return v === "light" || v === "dark" ? v : null;
}

export function applyStoredTheme() {
  const t = readTheme();
  if (t) document.documentElement.dataset.theme = t;
}

export default function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(readTheme);

  useEffect(() => {
    const root = document.documentElement;
    if (theme) root.dataset.theme = theme;
    else delete root.dataset.theme;
    try {
      const ls = safeStorage("local");
      if (theme) ls?.setItem("theme", theme);
      else ls?.removeItem("theme");
    } catch {
      // ignore
    }
  }, [theme]);

  const current = theme ?? "system";
  return (
    <button
      type="button"
      className="btn"
      onClick={() => setTheme(NEXT[current])}
      aria-label={`Theme: ${LABEL[current]}. Switch theme`}
    >
      Theme: {LABEL[current]}
    </button>
  );
}
