import assert from "node:assert/strict";
import {GestureController, type GestureCallbacks} from "../src/lib/gestures.ts";

let clock = 100;
let timer = 1;
Object.defineProperty(globalThis, "performance", {
  configurable: true,
  value: {now: () => clock},
});
Object.defineProperty(globalThis, "window", {
  configurable: true,
  value: {
    setTimeout: (_cb: () => void, _ms: number) => timer++,
    clearTimeout: (_id: number) => {},
  },
});
Object.defineProperty(globalThis, "requestAnimationFrame", {
  configurable: true,
  value: (_cb: () => void) => timer++,
});
Object.defineProperty(globalThis, "cancelAnimationFrame", {
  configurable: true,
  value: (_id: number) => {},
});

type Handler = (event: any) => void;
class FakeSurface {
  listeners = new Map<string, Handler>();
  addEventListener(type: string, handler: Handler) { this.listeners.set(type, handler); }
  removeEventListener(type: string) { this.listeners.delete(type); }
  setPointerCapture(_id: number) {}
  releasePointerCapture(_id: number) {}
  getBoundingClientRect() { return {left: 0, top: 0, width: 390, height: 844}; }
  emit(type: string, pointerId: number, clientX: number, clientY: number) {
    this.listeners.get(type)?.({pointerId, clientX, clientY, preventDefault() {}});
  }
}

const surface = new FakeSurface();
const clicks: {button: string; x: number; y: number}[] = [];
const doubles: {x: number; y: number}[] = [];
const cb: GestureCallbacks = {
  click: (button, x, y) => clicks.push({button, x, y}),
  dblclick: (x, y) => doubles.push({x, y}),
  moveCursor: () => {}, dragStart: () => {}, dragMove: () => {}, dragEnd: () => {},
  scroll: () => {}, zoomAt: () => {}, panBy: () => {}, cursorAt: () => {},
};
const gestures = new GestureController(surface as unknown as HTMLElement,
  (x, y) => ({x: x / 390, y: y / 844}), () => 1, cb);

const tap = (id: number, x: number, y: number, downAt: number, upAt: number) => {
  clock = downAt; surface.emit("pointerdown", id, x, y);
  clock = upAt; surface.emit("pointerup", id, x, y);
};

tap(1, 100, 200, 100, 140);
assert.equal(clicks.length, 1, "one tap must respond immediately with one click");

// Four CSS pixels of thumb wobble can be much larger on the remote desktop. The second click is
// deliberately pinned to the first point, yielding exactly a two-click pair at one position.
tap(2, 104, 203, 230, 270);
assert.equal(clicks.length, 2, "a double-tap must total two clicks, not three");
assert.equal(doubles.length, 0, "the second tap must not add the agent's two-click dblclick verb");
assert.deepEqual(clicks[1], clicks[0], "both clicks of a touch double-tap must share one point");

// Outside the recognition window the next tap is independent and lands where it was aimed.
tap(3, 220, 300, 700, 740);
assert.equal(clicks.length, 3, "a later tap remains a normal single click");
assert.notDeepEqual(clicks[2], clicks[1], "an independent tap must not be pinned to an old point");

gestures.destroy();
console.log("PASS: touch taps are immediate and double-tap totals exactly two same-point clicks");
