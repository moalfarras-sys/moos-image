/** Deterministic browser/time adapter; it never injects input into the running desktop. */
type Handler = (event: any) => void;
export class FakeSurface {
  listeners = new Map<string, Set<Handler>>();
  captures = new Set<number>();
  hidden = false;
  pointerLockElement: unknown = null;
  tagName = "CANVAS";
  isContentEditable = false;
  focused = false;
  addEventListener(type: string, handler: Handler) {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set());
    this.listeners.get(type)!.add(handler);
  }
  removeEventListener(type: string, handler: Handler) { this.listeners.get(type)?.delete(handler); }
  setPointerCapture(id: number) { this.captures.add(id); }
  releasePointerCapture(id: number) { this.captures.delete(id); }
  getBoundingClientRect() { return {left: 0, top: 0, width: 390, height: 844}; }
  focus() { this.focused = true; }
  emit(type: string, values: Record<string, unknown> = {}) {
    const event = {
      target: this, clientX: 100, clientY: 200, pointerId: 1, pointerType: "touch",
      button: 0, buttons: 0, key: "", code: "", repeat: false, ctrlKey: false,
      metaKey: false, altKey: false, shiftKey: false, isComposing: false,
      getModifierState: () => false, defaultPrevented: false,
      preventDefault() { this.defaultPrevented = true; }, ...values,
    };
    for (const handler of this.listeners.get(type) ?? []) handler(event);
    return event;
  }
}

export function inputEnvironment() {
  let clock = 100, nextId = 1;
  const frames = new Map<number, (time: number) => void>();
  const timers = new Map<number, {at: number; cb: () => void}>();
  const window = new FakeSurface(), document = new FakeSurface();
  const values = {
    performance: {now: () => clock},
    window: Object.assign(window, {
      setTimeout: (cb: () => void, ms: number) => {
        const id = nextId++; timers.set(id, {at: clock + ms, cb}); return id;
      },
      clearTimeout: (id: number) => timers.delete(id),
    }), document, navigator: {keyboard: {unlock() {}}},
    requestAnimationFrame: (cb: (time: number) => void) => {
      const id = nextId++; frames.set(id, cb); return id;
    },
    cancelAnimationFrame: (id: number) => frames.delete(id),
  };
  for (const [key, value] of Object.entries(values))
    Object.defineProperty(globalThis, key, {configurable: true, value});
  return {
    window, document,
    advance(ms: number) {
      clock += ms;
      for (const [id, timer] of [...timers]) {
        if (timer.at <= clock) { timers.delete(id); timer.cb(); }
      }
    },
    frame(ms = 16.67) {
      clock += ms;
      const batch = [...frames.values()]; frames.clear();
      for (const callback of batch) callback(clock);
    },
    pendingFrames: () => frames.size,
  };
}
