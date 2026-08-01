import { useEffect, useState } from "react";
import { getStatus, logout, tokenStore } from "./lib/api";
import { SetupScreen, LoginScreen } from "./ui/AuthScreens";
import { RemoteScreen } from "./ui/RemoteScreen";

type View =
  | { name: "loading" }
  | { name: "setup" }
  | { name: "login"; lockout: number }
  | { name: "remote"; token: string; hostPowerAllowed: boolean }
  | { name: "error"; message: string };

export default function App() {
  const [view, setView] = useState<View>({ name: "loading" });

  const decide = async () => {
    try {
      const s = await getStatus();
      if (s.firstRun) return setView({ name: "setup" });
      const tok = tokenStore.get();
      if (tok) return setView({ name: "remote", token: tok, hostPowerAllowed: s.hostPowerAllowed !== false });
      return setView({ name: "login", lockout: s.locked ? s.lockoutSeconds : 0 });
    } catch {
      setView({ name: "error", message: "Cannot reach the PC. Is the agent running and Tailscale connected?" });
    }
  };

  useEffect(() => {
    decide();
  }, []);

  const enterRemote = async (token: string) => {
    tokenStore.set(token);
    const status = await getStatus();
    setView({ name: "remote", token, hostPowerAllowed: status.hostPowerAllowed !== false });
  };

  const exitToLogin = async () => {
    const token = view.name === "remote" ? view.token : tokenStore.get();
    setView({ name: "loading" });
    // Sign out means server-side revocation, not merely forgetting the bearer in this tab. Keep
    // the local clear inside logout() even when the request fails, so offline exit remains instant.
    if (token) await logout(token);
    else tokenStore.clear();
    await decide();
  };

  switch (view.name) {
    case "loading":
      return (
        <div className="center-msg" style={{ position: "fixed", inset: 0 }}>
          <div className="spinner" />
          <div>Connecting…</div>
        </div>
      );
    case "error":
      return (
        <div className="center-msg" style={{ position: "fixed", inset: 0 }}>
          <div style={{ fontSize: 40 }}>🔌</div>
          <div style={{ maxWidth: 300 }}>{view.message}</div>
          <button className="btn" onClick={decide}>Retry</button>
        </div>
      );
    case "setup":
      return <SetupScreen onDone={enterRemote} />;
    case "login":
      return <LoginScreen onDone={enterRemote} lockoutSeconds={view.lockout} />;
    case "remote":
      return <RemoteScreen token={view.token} hostPowerAllowed={view.hostPowerAllowed} onExit={exitToLogin} />;
  }
}
