import { useEffect, useState } from "react";
import {
  deviceStore, getStatus, logout, resumeTrustedDevice, tokenStore, validateSession,
  type AuthResult,
} from "./lib/api";
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
      if (s.firstRun) {
        tokenStore.clear(); deviceStore.clear();
        return setView({ name: "setup" });
      }
      const tok = tokenStore.get();
      if (tok && await validateSession(tok))
        return setView({ name: "remote", token: tok, hostPowerAllowed: s.hostPowerAllowed !== false });
      tokenStore.clear();
      const remembered = deviceStore.get();
      if (remembered.id && remembered.token) {
        const resumed = await resumeTrustedDevice(remembered.id, remembered.token);
        if (resumed.ok && resumed.token) {
          tokenStore.set(resumed.token);
          return setView({ name: "remote", token: resumed.token, hostPowerAllowed: s.hostPowerAllowed !== false });
        }
        deviceStore.clear();
      }
      return setView({ name: "login", lockout: s.locked ? s.lockoutSeconds : 0 });
    } catch {
      setView({ name: "error", message: "Cannot reach the PC. Is the agent running and Tailscale connected?" });
    }
  };

  useEffect(() => {
    void decide();
  }, []);

  const enterRemote = async (grant: AuthResult) => {
    if (!grant.token) return;
    tokenStore.set(grant.token);
    if (grant.deviceId && grant.deviceToken) deviceStore.set(grant.deviceId, grant.deviceToken);
    setView({ name: "loading" });
    try {
      const status = await getStatus();
      setView({ name: "remote", token: grant.token, hostPowerAllowed: status.hostPowerAllowed !== false });
    } catch {
      // Keep the freshly issued token. Retry runs decide(), and as soon as status is reachable it
      // enters the remote without asking the user to type the PIN a second time.
      setView({ name: "error", message: "Access was approved, but the PC connection dropped. Reconnect and retry." });
    }
  };

  const retry = () => {
    setView({ name: "loading" });
    void decide();
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
        <div className="center-msg" style={{ position: "fixed", inset: 0 }} role="status" aria-live="polite">
          <div className="spinner" aria-hidden="true" />
          <div>Connecting…</div>
        </div>
      );
    case "error":
      return (
        <div className="center-msg" style={{ position: "fixed", inset: 0 }} role="alert">
          <div style={{ fontSize: 40 }} aria-hidden="true">🔌</div>
          <div style={{ maxWidth: 300 }}>{view.message}</div>
          <button className="btn" onClick={retry}>Retry</button>
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
