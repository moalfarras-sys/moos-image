import { useEffect, useState } from "react";

/**
 * usePwaInstall — surface the browser's own "install app" affordance as an
 * in-app, bilingual banner instead of relying on the browser menu item users
 * never find. Captures the one-shot beforeinstallprompt event, reports when
 * the app is already installed (display-mode standalone), and exposes
 * promptInstall() guarded by the captured event. No banner appears unless the
 * served page is a real installable PWA.
 */
export type PwaInstall = {
  canInstall: boolean;
  installed: boolean;
  promptInstall: () => void;
};

type InstallPromptEvent = Event & {
  prompt: () => void;
  userChoice?: Promise<{ outcome: string }>;
};

export function usePwaInstall(): PwaInstall {
  const [promptEvent, setPromptEvent] = useState<InstallPromptEvent | null>(null);
  const [installed, setInstalled] = useState(false);

  useEffect(() => {
    const standalone =
      window.matchMedia?.("(display-mode: standalone)").matches ||
      window.matchMedia?.("(display-mode: fullscreen)").matches ||
      (navigator as Navigator & { standalone?: boolean }).standalone === true;
    if (standalone) {
      setInstalled(true);
      return;
    }
    const onPrompt = (event: Event) => {
      event.preventDefault();
      setPromptEvent(event as InstallPromptEvent);
    };
    const onInstalled = () => {
      setInstalled(true);
      setPromptEvent(null);
    };
    window.addEventListener("beforeinstallprompt", onPrompt);
    window.addEventListener("appinstalled", onInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onPrompt);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  const promptInstall = () => {
    if (!promptEvent) return;
    void promptEvent.prompt();
    void promptEvent.userChoice?.then(() => setPromptEvent(null));
  };

  return { canInstall: promptEvent !== null, installed, promptInstall };
}
