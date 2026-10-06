import type { RemoteModel } from "./model";
import { IconBackspace, IconCopy, IconEnter, IconKeyboardHide, IconLock, IconPaste } from "../icons";

const F_KEYS = Array.from({ length: 12 }, (_, i) => `F${i + 1}`);

/**
 * Typing on the computer from a phone.
 *
 * The phone's OWN keyboard does the typing — every language and layout it has, dictation, swipe,
 * autocorrect — through one real text field, diffed into the remote as words, Backspaces and
 * Enter (lib/typing.ts). What a phone keyboard does not have sits in two rows above it:
 *
 *   row 1  Password · Ctrl Alt Shift Meta · Esc Tab · arrows · Home End PgUp PgDn Del
 *   row 2  Copy to this device · Paste from this device · Select all · Undo · Redo · Cut · F1–F12
 *
 * Ctrl/Alt/Shift/Meta are one-shot: tap Ctrl, then C, and Ctrl+C is sent. Every button defends the
 * text field's focus on pointerdown (keepFocus), because on Android a button that takes focus
 * dismisses the keyboard — sending Ctrl+C must not cost the keyboard.
 */
export function KeyboardPanel({ m }: { m: RemoteModel }) {
  const { tr, keepFocus } = m;
  const secret = m.secureTyping || m.hostLocked === true;
  const held = [...m.mods];
  const meta = m.hostKind === "windows" ? "Win" : "Meta";
  const redo = m.hostKind === "windows" ? ["Control", "Y"] : ["Control", "Shift", "Z"];
  const key = (label: string, onClick: () => void, extra = "", aria?: string) => (
    <button key={label} type="button" {...keepFocus} className={"kkey " + extra} aria-label={aria}
            onClick={onClick}>{label}</button>
  );
  return (
    <div className={"kbbar" + (m.kbOpen ? " open" : "")} ref={m.kbbarRef} inert={!m.kbOpen} aria-hidden={!m.kbOpen}>
      <div className="keyrow" role="toolbar" aria-label={tr("modifierKeys")}>
        <button type="button" {...keepFocus} className={"kkey secure" + (secret ? " on" : "")}
                aria-pressed={secret} disabled={!m.secureKeyboardAvailable || m.hostLocked === true}
                onClick={m.toggleSecureTyping}>
          <IconLock /><span>{tr("secureTyping")}</span>
        </button>
        <span className="kdiv" aria-hidden="true" />
        {(["Control", "Alt", "Shift", "Meta"] as const).map((mod) => (
          <button key={mod} type="button" {...keepFocus} className={"kkey mod" + (m.mods.has(mod) ? " on" : "")}
                  aria-pressed={m.mods.has(mod)} onClick={() => m.toggleMod(mod)}>
            {mod === "Control" ? "Ctrl" : mod === "Meta" ? meta : mod}
          </button>
        ))}
        <span className="kdiv" aria-hidden="true" />
        {key("Esc", () => m.sendKey("Escape"))}
        {key("Tab", () => m.sendKey("Tab"))}
        {key("←", () => m.sendKey("ArrowLeft"), "arrow", tr("arrowLeft"))}
        {key("↑", () => m.sendKey("ArrowUp"), "arrow", tr("arrowUp"))}
        {key("↓", () => m.sendKey("ArrowDown"), "arrow", tr("arrowDown"))}
        {key("→", () => m.sendKey("ArrowRight"), "arrow", tr("arrowRight"))}
        <span className="kdiv" aria-hidden="true" />
        {key("Home", () => m.sendKey("Home"))}
        {key("End", () => m.sendKey("End"))}
        {key("PgUp", () => m.sendKey("PageUp"))}
        {key("PgDn", () => m.sendKey("PageDown"))}
        {key("Del", () => m.sendKey("Delete"))}
      </div>
      <div className="keyrow edit" role="toolbar" aria-label={tr("editKeys")}>
        <button type="button" {...keepFocus} className="kkey action" onClick={() => void m.copyFromPc()}>
          <IconCopy /><span>{tr("copyToThisDevice")}</span>
        </button>
        <button type="button" {...keepFocus} className="kkey action" onClick={() => void m.pasteFromDevice()}>
          <IconPaste /><span>{tr("pasteFromThisDevice")}</span>
        </button>
        {key(tr("selectAll"), () => m.sendShortcut(["Control", "A"]))}
        {key(tr("undo"), () => m.sendShortcut(["Control", "Z"]))}
        {key(tr("redo"), () => m.sendShortcut(redo))}
        {key(tr("cut"), () => m.sendShortcut(["Control", "X"]))}
        <span className="kdiv" aria-hidden="true" />
        {F_KEYS.map((f) => key(f, () => m.sendKey(f), "fkey"))}
      </div>
      <div className="kbinput-row">
        <div className="kbfield">
          {held.length > 0 && (
            <span className="kbheld" aria-live="polite">
              {tr("heldPrefix")} {held.map((h) => (h === "Control" ? "Ctrl" : h === "Meta" ? meta : h)).join("+")}+
            </span>
          )}
          <input
            ref={m.inputRef} className="kbinput" type={secret ? "password" : "text"} inputMode="text" dir="auto"
            autoCapitalize="off" autoCorrect="off" autoComplete="off" spellCheck={false}
            placeholder={tr("typeHere")} aria-label={tr("typeHere")}
            onInput={m.onInput} onKeyDown={m.onInputKeyDown}
            onCompositionStart={m.onCompositionStart} onCompositionEnd={m.onCompositionEnd}
            onBlur={m.onInputBlur}
          />
        </div>
        <button type="button" {...keepFocus} className="kbicon" onClick={() => m.sendKey("Backspace")}
                aria-label="Backspace"><IconBackspace /></button>
        <button type="button" {...keepFocus} className="kbicon enter" onClick={() => m.sendKey("Enter")}
                aria-label="Enter"><IconEnter /></button>
        <button type="button" {...keepFocus} className="kbdone" onClick={m.closeKeyboard}
                title={tr("hideKeyboard")}>
          <IconKeyboardHide /><span>{tr("done")}</span>
        </button>
      </div>
    </div>
  );
}
