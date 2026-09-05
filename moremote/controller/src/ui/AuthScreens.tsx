import { useEffect, useRef, useState } from "react";
import { login, setupPin, type AuthResult } from "../lib/api";
import { BUILD } from "../types";
import { IconBackspace, IconEnter, IconLock } from "./icons";
import { detectLang, makeT } from "../lib/i18n";

const tr = makeT(detectLang());

function Brand({ subtitle }: { subtitle: string }) {
  return (
    <div className="brand">
      <div className="brand-logo">
        <img src="/icons/brand-logo.png" alt="Mo Remote" />
      </div>
      <div>
        <h1>Mo Remote</h1>
        <p>{subtitle}</p>
      </div>
    </div>
  );
}

function Signature() {
  return (
    <div className="signature">
      by <b>Moalfarras</b> · <span style={{ color: "var(--ok)" }}>{BUILD}</span>
    </div>
  );
}

function defaultDeviceName() {
  const ua = navigator.userAgent;
  if (/iPad/i.test(ua)) return "iPad";
  if (/iPhone/i.test(ua)) return "iPhone";
  if (/Android/i.test(ua)) return tr("androidPhone");
  if (/Windows/i.test(ua)) return tr("windowsDevice");
  if (/Macintosh/i.test(ua)) return "Mac";
  if (/Linux/i.test(ua)) return tr("linuxDevice");
  return tr("myDevice");
}

function TrustDevice({ checked, onChange }: { checked: boolean; onChange: (value: boolean) => void }) {
  return (
    <label className="trust-device">
      <input type="checkbox" checked={checked} onChange={e => onChange(e.target.checked)} />
      <span><b>{tr("trustDevice")}</b><small>{tr("trustDeviceHint")}</small></span>
    </label>
  );
}

function PinDots({ count, error }: { count: number; error?: boolean }) {
  const shown = Math.max(6, count);
  return (
    <div
      className={"pin-dots" + (error ? " error" : "")}
      role="status"
      aria-label={`${count} PIN digits entered`}
    >
      {Array.from({ length: shown }).map((_, i) => (
        <i key={i} className={i < count ? "on" : ""} />
      ))}
    </div>
  );
}

function Keypad({
  onDigit,
  onBackspace,
  onSubmit,
  canSubmit,
  disabled = false,
}: {
  onDigit: (d: string) => void;
  onBackspace: () => void;
  onSubmit: () => void;
  canSubmit: boolean;
  disabled?: boolean;
}) {
  const tap = (fn: () => void) => () => {
    if ("vibrate" in navigator) navigator.vibrate?.(8);
    fn();
  };
  useEffect(() => {
    if (disabled) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.ctrlKey || event.altKey || event.metaKey) return;
      if (event.target instanceof HTMLButtonElement
          && (event.key === "Enter" || event.key === " ")) return;
      if (/^[0-9]$/.test(event.key)) {
        event.preventDefault();
        onDigit(event.key);
      } else if (event.key === "Backspace" || event.key === "Delete") {
        event.preventDefault();
        onBackspace();
      } else if (event.key === "Enter" && canSubmit) {
        event.preventDefault();
        onSubmit();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [canSubmit, disabled, onBackspace, onDigit, onSubmit]);

  return (
    <div className="keypad" aria-disabled={disabled}>
      {["1", "2", "3", "4", "5", "6", "7", "8", "9"].map((d) => (
        <button key={d} className="key" onClick={tap(() => onDigit(d))} disabled={disabled}>
          {d}
        </button>
      ))}
      <button className="key wide" onClick={tap(onBackspace)} disabled={disabled} aria-label={tr("backspaceAria")}>
        <IconBackspace />
      </button>
      <button className="key" onClick={tap(() => onDigit("0"))} disabled={disabled}>
        0
      </button>
      <button className="key accent" onClick={tap(onSubmit)} disabled={disabled || !canSubmit} aria-label={tr("confirmPrefix")}>
        <IconEnter />
      </button>
    </div>
  );
}

export function SetupScreen({ onDone }: { onDone: (grant: AuthResult) => Promise<void> }) {
  const [step, setStep] = useState<"create" | "confirm">("create");
  const [first, setFirst] = useState("");
  const [pin, setPin] = useState("");
  const [hint, setHint] = useState(tr("pinChoose"));
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState(false);
  const [trustDevice, setTrustDevice] = useState(true);

  const add = (d: string) => {
    setError(false);
    setPin((p) => (p.length >= 10 ? p : p + d));
  };
  const back = () => {
    setError(false);
    setPin((p) => p.slice(0, -1));
  };

  const submit = async () => {
    if (pin.length < 6 || busy) return;
    if (step === "create") {
      setFirst(pin);
      setPin("");
      setStep("confirm");
      setHint(tr("pinConfirm"));
      return;
    }
    if (pin !== first) {
      setError(true);
      setHint(tr("pinMismatch"));
      setPin("");
      setStep("create");
      setFirst("");
      return;
    }
    setBusy(true);
    let handedOff = false;
    try {
      const r = await setupPin(pin, trustDevice, defaultDeviceName());
      if (r.ok && r.token) {
        handedOff = true;
        await onDone(r);
        return;
      }
      setError(true);
      setHint(tr("pinSaveFailed"));
    } catch {
      setError(true);
      setHint(tr("connectionDropped"));
    } finally {
      if (!handedOff) setBusy(false);
    }
  };

  return (
    <div className="auth" aria-busy={busy}>
      <Brand subtitle={step === "create" ? tr("pinSetup") : tr("pinConfirmTitle")} />
      <PinDots count={pin.length} error={error} />
      <div className={"hint" + (error ? " error" : "")} role={error ? "alert" : "status"}>{hint}</div>
      <TrustDevice checked={trustDevice} onChange={setTrustDevice} />
      <Keypad onDigit={add} onBackspace={back} onSubmit={submit}
              canSubmit={pin.length >= 6 && !busy} disabled={busy} />
      <Signature />
    </div>
  );
}

export function LoginScreen({ onDone, lockoutSeconds }: { onDone: (grant: AuthResult) => Promise<void>; lockoutSeconds: number }) {
  const [pin, setPin] = useState("");
  const [hint, setHint] = useState(tr("pinEnter"));
  const [error, setError] = useState(false);
  const [locked, setLocked] = useState(lockoutSeconds);
  const [busy, setBusy] = useState(false);
  const [trustDevice, setTrustDevice] = useState(true);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    if (locked <= 0) return;
    setHint(`${tr("locked")} ${locked}s`);
    timer.current = window.setInterval(() => {
      setLocked((s) => {
        if (s <= 1) {
          window.clearInterval(timer.current!);
          setHint(tr("pinEnter"));
          return 0;
        }
        setHint(`${tr("locked")} ${s - 1}s`);
        return s - 1;
      });
    }, 1000);
    return () => {
      if (timer.current) window.clearInterval(timer.current);
    };
  }, [locked > 0]);

  const add = (d: string) => {
    if (locked > 0) return;
    setError(false);
    setPin((p) => (p.length >= 12 ? p : p + d));
  };
  const back = () => {
    setError(false);
    setPin((p) => p.slice(0, -1));
  };

  const submit = async () => {
    if (pin.length < 6 || busy || locked > 0) return;
    setBusy(true);
    let handedOff = false;
    try {
      const r = await login(pin, trustDevice, defaultDeviceName());
      setPin("");
      if (r.ok && r.token) {
        handedOff = true;
        await onDone(r);
      } else if (r.error === "locked") {
        setLocked(r.lockoutSeconds || 300);
      } else {
        setError(true);
        setHint(tr("pinWrong"));
      }
    } catch {
      setError(true);
      setHint(tr("connectionDropped"));
    } finally {
      if (!handedOff) setBusy(false);
    }
  };

  return (
    <div className="auth" aria-busy={busy}>
      <Brand subtitle={tr("privateRemote")} />
      <PinDots count={pin.length} error={error} />
      <div className={"hint" + (error ? " error" : locked > 0 ? " error" : "")}
           role={error ? "alert" : "status"} aria-live={locked > 0 ? "off" : "polite"}>
        {locked > 0 && <IconLock className="" />} {hint}
      </div>
      <TrustDevice checked={trustDevice} onChange={setTrustDevice} />
      <Keypad onDigit={add} onBackspace={back} onSubmit={submit}
              canSubmit={pin.length >= 6 && locked <= 0 && !busy}
              disabled={busy || locked > 0} />
      <Signature />
    </div>
  );
}
