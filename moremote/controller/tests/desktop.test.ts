import assert from "node:assert/strict";
import {test} from "node:test";
import {DesktopInput, type DesktopCallbacks} from "../src/lib/desktop.ts";
import {FakeSurface, inputEnvironment} from "./input-harness.ts";

function setup() {
  const env = inputEnvironment(), surface = new FakeSurface();
  const output: {kind: string; values: unknown[]}[] = [];
  const record = (kind: string) => (...values: unknown[]) => output.push({kind, values});
  const cb: DesktopCallbacks = {
    move: record("move"), moveRelative: record("relative"), down: record("down"), up: record("up"),
    scroll: record("scroll"), keyCode: record("key"), text: record("text"),
    cursorAt: record("cursor"), pasteIntent: record("paste"),
  };
  const desktop = new DesktopInput(surface as unknown as HTMLElement,
    (x, y) => ({x: Math.min(1, Math.max(0, x / 390)), y: Math.min(1, Math.max(0, y / 844))}),
    cb, () => 1, () => false, (_x, y) => y >= 300 && y <= 500);
  desktop.attach();
  const mouse = (type: string, x = 100, y = 350, button = 0) =>
    (type === "mouseup" ? env.window : surface).emit(type, {clientX: x, clientY: y, button});
  const key = (type: string, key: string, code: string, extra = {}) =>
    env.window.emit(type, {target: surface, key, code, ...extra});
  const events = (kind: string) => output.filter(item => item.kind === kind).map(item => item.values);
  return {env, surface, desktop, mouse, key, events, output};
}

test("all three mouse buttons press/release at the latest point", () => {
  const h = setup();
  for (let button = 0; button < 3; button++) {
    h.mouse("mousemove", 50, 350); h.mouse("mousedown", 100, 350, button);
    assert.deepEqual(h.events("cursor").at(-1), [100 / 390, 350 / 844]);
    h.mouse("mousemove", 150, 360); h.mouse("mouseup", 200, 400, button);
    assert.deepEqual(h.events("cursor").at(-1), [200 / 390, 400 / 844]);
  }
  assert.deepEqual(h.events("down").map(values => values[0]), ["left", "middle", "right"]);
  assert.deepEqual(h.events("up").map(values => values[0]), ["left", "middle", "right"]);
  h.desktop.destroy();
});

test("letterbox clicks/hover/wheel do not hit desktop edges; a started drag can leave", () => {
  const h = setup();
  h.mouse("mousemove", 100, 100); h.mouse("mousedown", 100, 100); h.mouse("mouseup", 100, 100);
  h.surface.emit("wheel", {clientY: 100, deltaMode: 0, deltaX: 0, deltaY: 100});
  h.env.frame(); assert.equal(h.output.length, 0);
  h.mouse("mousedown");
  h.env.window.emit("mousemove", {clientX: 450, clientY: 100}); h.env.frame();
  assert.deepEqual(h.events("move").at(-1), [1, 100 / 844]);
  h.mouse("mouseup", 450, 100);
  assert.deepEqual(h.events("up"), [["left", 1, 100 / 844]]);
  h.desktop.destroy();
});

for (const reason of ["blur", "hidden", "detach", "unlock"] as const) {
  test(`${reason} releases held keys/buttons once and discards queued motion/scroll`, () => {
    const h = setup();
    if (reason === "unlock") { h.env.document.pointerLockElement = h.surface; h.env.document.emit("pointerlockchange"); }
    h.mouse("mousedown"); h.key("keydown", "Control", "ControlLeft", {ctrlKey: true});
    h.mouse("mousemove", 200, 360);
    h.surface.emit("wheel", {clientY: 350, deltaMode: 0, deltaX: 0, deltaY: 100});
    if (reason === "blur") h.env.window.emit("blur");
    if (reason === "hidden") { h.env.document.hidden = true; h.env.document.emit("visibilitychange"); }
    if (reason === "detach") h.desktop.detach();
    if (reason === "unlock") { h.env.document.pointerLockElement = null; h.env.document.emit("pointerlockchange"); }
    const count = h.output.length;
    h.env.frame(); h.desktop.releaseAll();
    assert.equal(h.output.length, count);
    assert.equal(h.events("up").length, 1);
    assert.deepEqual(h.events("key"), [["ControlLeft", true], ["ControlLeft", false]]);
    assert.equal(h.events("scroll").length, 0);
    h.desktop.destroy();
  });
}

test("pointer lock coalesces relative movement and does not send an old absolute warp", () => {
  const h = setup(); h.mouse("mousemove", 150, 350);
  h.env.document.pointerLockElement = h.surface; h.env.document.emit("pointerlockchange");
  h.surface.emit("mousemove", {movementX: 4, movementY: -2});
  h.surface.emit("mousemove", {movementX: 6, movementY: 3}); h.env.frame();
  assert.deepEqual(h.events("relative"), [[10, 1]]);
  assert.equal(h.events("move").length, 0);
  h.desktop.destroy();
});

test("wheel targets the hovered remote point and supports fractional and line deltas", () => {
  const h = setup();
  h.surface.emit("wheel", {clientX: 150, clientY: 350, deltaMode: 0, deltaX: 0, deltaY: 0.6});
  h.env.frame();
  assert.deepEqual(h.events("move"), [[150 / 390, 350 / 844]]);
  assert.deepEqual(h.events("scroll"), [[0, 0.04]]);
  h.surface.emit("wheel", {clientY: 350, deltaMode: 1, deltaX: 0, deltaY: 3}); h.env.frame();
  const lines = Number(h.events("scroll").at(-1)![1]);
  h.surface.emit("wheel", {clientY: 350, deltaMode: 0, deltaX: 0, deltaY: 100}); h.env.frame();
  assert.equal(Number(h.events("scroll").at(-1)![1]), lines);
  h.desktop.destroy();
});

test("physical repeats stay held and release even after focus enters a local field", () => {
  const h = setup();
  h.key("keydown", "a", "KeyA"); h.key("keydown", "a", "KeyA", {repeat: true});
  h.key("keyup", "a", "KeyA", {target: {tagName: "TEXTAREA"}});
  assert.deepEqual(h.events("key"), [["KeyA", true], ["KeyA", false]]);
  h.key("keydown", "b", "KeyB", {target: {tagName: "INPUT", type: "text"}});
  assert.equal(h.events("key").length, 2);
  h.desktop.destroy();
});

test("local buttons, sliders, dialogs and already-handled Escape retain their keyboard events", () => {
  const h = setup();
  for (const target of [
    {tagName: "BUTTON"}, {tagName: "INPUT", type: "range"},
    {tagName: "SPAN", closest: () => ({role: "dialog"})},
  ]) {
    const event = h.key("keydown", " ", "Space", {target});
    assert.equal(event.defaultPrevented, false);
  }
  h.key("keydown", "Escape", "Escape", {defaultPrevented: true});
  assert.equal(h.events("key").length, 0);
  h.mouse("mousedown"); h.mouse("mouseup");
  h.key("keydown", "a", "KeyA"); h.key("keyup", "a", "KeyA");
  assert.deepEqual(h.events("key"), [["KeyA", true], ["KeyA", false]], "canvas focus restores physical typing");
  h.desktop.destroy();
});

test("Arabic text and AltGr characters reach the character path without modifier chords", () => {
  const h = setup();
  h.key("keydown", "ش", "KeyA"); h.key("keyup", "ش", "KeyA");
  h.key("keydown", "Control", "ControlLeft", {ctrlKey: true});
  const altGraph = {ctrlKey: true, altKey: true, getModifierState: (name: string) => name === "AltGraph"};
  h.key("keydown", "AltGraph", "AltRight", altGraph);
  h.key("keydown", "@", "KeyQ", altGraph); h.key("keyup", "@", "KeyQ", altGraph);
  assert.deepEqual(h.events("text"), [["ش"], ["@"]]);
  assert.deepEqual(h.events("key"), [["ControlLeft", true], ["ControlLeft", false]]);
  h.desktop.destroy();
});

test("dead/composition placeholder keys do not inject their physical position", () => {
  const h = setup();
  for (const name of ["Dead", "Process", "Unidentified"])
    h.key("keydown", name, "Quote");
  h.key("keydown", "é", "KeyE");
  assert.deepEqual(h.events("text"), [["é"]]);
  assert.equal(h.events("key").length, 0);
  h.desktop.destroy();
});

test("Ctrl+V on an Arabic layout invokes the clipboard bridge without a physical V", () => {
  const h = setup();
  const event = h.key("keydown", "ر", "KeyV", {ctrlKey: true});
  assert.equal(h.events("paste").length, 1);
  assert.equal(h.events("key").length, 0);
  assert.equal(event.defaultPrevented, false, "the browser paste event must still be allowed");
  h.desktop.destroy();
});
