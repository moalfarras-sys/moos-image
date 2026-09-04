import { useEffect, useState } from "react";
import {
  deviceStore, getStatus, logout, resumeTrustedDevice, tokenStore, validateSession,
  type AuthResult,
} from "./lib/api";
import { SetupScreen, LoginScreen } from "./ui/AuthScreens";
import { RemoteScreen } from "./ui/RemoteScreen";
import { IconPlug } from "./ui/icons";
import { usePwaInstall } from "./lib/pwa";
import { initLang, setLang, makeT, type Lang } from "./lib/i18n";

type View =
  | { name: "loading" }
  | { name: "setup" }
  | { name: "login"; lockout: number }
  | { name: "remote"; token: string; hostPowerAllowed: boolean }
  | { name: "error"; message: string };

export default function App() {
  const [view, setView] = useState<View>({ name: "loading" });
  const pwa = usePwaInstall();
  const [lang, setLangState] = useState<Lang>(() => initLang());
  const tt = makeT(lang);

  const switchLang = (next: Lang) => {
    setLang(next);
    setLangState(next);
  };

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

  // The access token aged out mid-session (60-minute sliding TTL) and the agent said
  // "unauthorized". This is NOT a sign-out: the old path routed it through exitToLogin, whose
  // logout() revokes the trusted-device credential too — destroying, on every expiry, the very
  // credential that exists to survive expiry, and putting the owner back at the PIN pad each
  // hour. Drop only the dead access token and re-decide: the device credential mints a fresh
  // session silently, and the PIN pad is the fallthrough, not the destination.
  const authExpired = () => {
    tokenStore.clear();
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
          <IconPlug className="error-glyph" />
          <div style={{ maxWidth: 300 }}>{view.message}</div>
          <button className="btn" onClick={retry}>Retry</button>
        </div>
      );
    case "setup":
      return (
        <>
          {pwa.canInstall && <InstallBanner onInstall={pwa.promptInstall} tt={tt} />}
          <SetupScreen onDone={enterRemote} />
        </>
      );
    case "login":
      return (
        <>
          {pwa.canInstall && <InstallBanner onInstall={pwa.promptInstall} tt={tt} />}
          <LoginScreen onDone={enterRemote} lockoutSeconds={view.lockout} />
        </>
      );
    case "remote":
      return <RemoteScreen token={view.token} hostPowerAllowed={view.hostPowerAllowed} onExit={exitToLogin} onAuthExpired={authExpired} lang={lang} onLangSwitch={switchLang} />;
  }
}

function InstallBanner({ onInstall, tt }: { onInstall: () => void; tt: (id: Parameters<ReturnType<typeof makeT>>[0]) => string }) {
  return (
    <div
      style={{
        position: "fixed", bottom: 14, left: 14, right: 14, zIndex: 40,
        display: "flex", gap: 10, alignItems: "center", justifyContent: "space-between",
        padding: "10px 12px", borderRadius: 14,
        background: "rgba(20,25,28,.92)", border: "1px solid rgba(78,200,200,.35)",
        boxShadow: "0 8px 24px rgba(0,0,0,.45)", color: "#e8f1f1",
      }}
      role="status"
    >
      <span style={{ fontSize: 13 }}>{tt("installBanner")}</span>
      <button className="btn" onClick={onInstall} style={{ flexShrink: 0 }}>
        {tt("install")}
      </button>
    </div>
  );
}
