import assert from "node:assert/strict";
import {test} from "node:test";
import {GestureController, type GestureCallbacks} from "../src/lib/gestures.ts";
import {FakeSurface, inputEnvironment} from "./input-harness.ts";

function setup(options: {mode?: "touch" | "direct" | "trackpad"; rotated?: boolean;
  relative?: boolean; pan?: {x: boolean; y: boolean}; inContent?: (x: number, y: number) => boolean} = {}) {
  const env = inputEnvironment();
  const surface = new FakeSurface();
  const output: {kind: string; values: unknown[]}[] = [];
  const record = (kind: string) => (...values: unknown[]) => output.push({kind, values});
  const cb: GestureCallbacks = {
    moveRelative: record("relative"), click: record("click"), dblclick: record("dblclick"), moveCursor: record("move"),
    dragStart: record("down"), dragMove: record("drag"), dragEnd: record("up"),
    scroll: record("scroll"), zoomAt: record("zoom"), panBy: record("pan"), cursorAt: record("cursor"),
    zoomToggleAt: record("toggle"), dismissContext: record("dismiss"),
  };
  const gestures = new GestureController(surface as unknown as HTMLElement,
    (x, y) => ({x: Math.min(1, Math.max(0, x / 390)), y: Math.min(1, Math.max(0, y / 844))}),
    () => 1, cb, () => 1, options.inContent,
    () => options.pan ?? {x: false, y: false}, () => options.rotated ?? false, () => options.relative ?? false);
  if (options.mode) gestures.setMode(options.mode);
  const pointer = (type: string, id: number, x: number, y: number) =>
    surface.emit(type, {pointerId: id, clientX: x, clientY: y});
  const down = (id = 1, x = 100, y = 200) => pointer("pointerdown", id, x, y);
  const move = (id = 1, x = 100, y = 200) => pointer("pointermove", id, x, y);
  const up = (id = 1, x = 100, y = 200) => pointer("pointerup", id, x, y);
  const tap = (x: number, y: number) => { down(1, x, y); env.advance(40); up(1, x, y); };
  const events = (kind: string) => output.filter(item => item.kind === kind).map(item => item.values);
  return {env, surface, gestures, down, move, up, tap, events, output};
}

test("touch taps are immediate; a double-tap totals exactly two same-point clicks", () => {
  const h = setup();
  h.tap(100, 200);
  assert.equal(h.events("click").length, 1);
  h.env.advance(90); h.tap(104, 203);
  assert.deepEqual(h.events("click"), [["left", 100 / 390, 200 / 844], ["left", 100 / 390, 200 / 844]]);
  assert.equal(h.events("dblclick").length, 0);
  assert.deepEqual(h.events("cursor").at(-1), [100 / 390, 200 / 844], "drawn cursor stays on the actual second click");
  h.env.advance(430); h.tap(220, 300);
  assert.deepEqual(h.events("click")[2], ["left", 220 / 390, 300 / 844]);
  h.gestures.destroy();
});

test("direct drag cannot begin in letterbox and leave the remote button held", () => {
  const h = setup({mode: "direct", inContent: (_x, y) => y >= 300 && y <= 500});
  h.down(1, 100, 200); h.move(1, 100, 350); h.up(1, 100, 350);
  assert.equal(h.events("down").length, 0);
  assert.equal(h.events("click").length, 0);
  h.down(1, 100, 350); h.move(1, 150, 200); h.up(1, 150, 200);
  assert.equal(h.events("down").length, 1);
  assert.equal(h.events("up").length, 1, "a drag starting on the image releases outside it");
  h.gestures.destroy();
});

test("a short trackpad cursor move never warps to the finger or clicks", () => {
  const h = setup({mode: "trackpad"});
  h.gestures.setCursor(0.75, 0.75);
  h.down(1, 20, 40); h.move(1, 35, 40); h.env.advance(60); h.up(1, 35, 40);
  assert.equal(h.events("click").length, 0);
  const [x, y] = h.events("move").at(-1)! as number[];
  assert.ok(x > 0.75 && x < 0.85); assert.equal(y, 0.75);
  h.tap(20, 40);
  assert.deepEqual(h.events("click"), [["left", x, y]], "trackpad taps click at the cursor");
  h.gestures.destroy();
});

test("a large swipe returning to its origin is not rescued as an accidental click", () => {
  const h = setup();
  h.down(); h.move(1, 100, 450); h.env.frame(); h.move(1, 100, 200); h.up();
  assert.equal(h.events("click").length, 0);
  assert.ok(h.events("scroll").length > 0);
  h.gestures.destroy();
});

test("pointerup's final drag position arrives before release", () => {
  const h = setup({mode: "direct"});
  h.down(); h.move(1, 140, 200); h.up(1, 180, 250);
  assert.deepEqual(h.events("up"), [[180 / 390, 250 / 844]]);
  assert.deepEqual(h.events("drag").at(-1), [180 / 390, 250 / 844]);
  h.gestures.destroy();
});

for (const reason of ["cancel", "capture", "blur", "hidden", "mode", "destroy"] as const) {
  test(`${reason} retires a drag, all captures, and queued input exactly once`, () => {
    const h = setup({mode: "direct"});
    h.down(); h.move(1, 150, 200);
    assert.equal(h.events("down").length, 1);
    if (reason === "cancel") h.surface.emit("pointercancel");
    if (reason === "capture") h.surface.emit("lostpointercapture");
    if (reason === "blur") h.env.window.emit("blur");
    if (reason === "hidden") { h.env.document.hidden = true; h.env.document.emit("visibilitychange"); }
    if (reason === "mode") h.gestures.setMode("trackpad");
    if (reason === "destroy") h.gestures.destroy();
    assert.equal(h.events("up").length, 1);
    assert.equal(h.events("drag").length, 0, "cancelled pending motion is discarded, not flushed");
    assert.equal(h.surface.captures.size, 0);
    const count = h.output.length;
    h.env.frame(); h.up(1, 150, 200);
    assert.equal(h.output.length, count, "nothing from the retired interaction can escape later");
    h.gestures.destroy();
    assert.equal(h.events("up").length, 1);
  });
}

test("a cancelled long press sends no context menu", () => {
  const h = setup(); h.down(); h.env.advance(510);
  h.surface.emit("pointercancel"); h.up();
  assert.equal(h.events("click").length, 0);
  h.gestures.destroy();
});

test("adding a second finger flushes a pending drag before releasing it", () => {
  const h = setup({mode: "direct"});
  h.down(); h.move(1, 150, 200); h.down(2, 200, 200); h.env.frame();
  const wire = h.output.filter(item => ["down", "drag", "up"].includes(item.kind));
  assert.deepEqual(wire.map(item => item.kind), ["down", "drag", "up"]);
  h.up(1, 150, 200); h.move(2, 240, 200); h.up(2, 240, 200);
  assert.equal(h.events("click").length, 0, "a remaining finger cannot turn the prior drag into a click");
  h.gestures.destroy();
});

test("two-finger tap tolerates jitter and waits for both fingers to lift", () => {
  const h = setup();
  h.down(1, 100, 200); h.down(2, 200, 200);
  for (let i = 0; i < 8; i++) {
    h.move(1, 100 + (i % 2 ? 2 : -2), 201); h.env.frame();
  }
  assert.equal(h.events("zoom").length, 0);
  assert.equal(h.events("scroll").length, 0);
  h.up(1, 102, 201); assert.equal(h.events("click").length, 0);
  h.up(2, 200, 200);
  assert.deepEqual(h.events("click"), [["right", 100 / 390, 200 / 844]]);
  assert.equal(h.events("toggle").length, 0, "first gesture near page load is not a double-tap");
  h.gestures.destroy();
});

test("parallel two-finger movement is coalesced without becoming a pinch", () => {
  const h = setup();
  h.down(1, 100, 200); h.down(2, 200, 200);
  h.move(1, 120, 200); h.move(2, 220, 200); h.env.frame();
  assert.equal(h.events("zoom").length, 0);
  assert.deepEqual(h.events("scroll"), [[20 / 24, 0]]);
  h.gestures.destroy();
});

test("rotated scrolling masks the fitting screen axis before translating to desktop axes", () => {
  const h = setup({rotated: true, pan: {x: true, y: false}});
  h.down(1, 100, 200); h.down(2, 200, 200);
  h.move(1, 120, 230); h.move(2, 220, 230); h.env.frame();
  assert.deepEqual(h.events("pan"), [[20, 0]]);
  assert.deepEqual(h.events("scroll"), [[-30 / 24, 0]]);
  h.gestures.destroy();
});

test("two-finger zoom shortcut dismisses context without clicking a menu item", () => {
  const h = setup();
  const twoTap = (x: number) => {
    h.down(1, x, 200); h.down(2, x + 100, 200); h.env.advance(40);
    h.up(1, x, 200); h.up(2, x + 100, 200);
  };
  twoTap(100); h.env.advance(60); twoTap(100);
  assert.equal(h.events("toggle").length, 1);
  assert.equal(h.events("dismiss").length, 1);
  assert.equal(h.events("click").length, 1);
  h.env.advance(30); twoTap(220);
  assert.equal(h.events("toggle").length, 1, "a different location is not the zoom shortcut");
  h.gestures.destroy();
});

test("a third touch cannot turn an interrupted pinch into a right click", () => {
  const h = setup();
  h.down(1, 100, 200); h.down(2, 200, 200); h.down(3, 250, 200);
  h.up(3, 250, 200); h.up(1, 100, 200); h.up(2, 200, 200);
  assert.equal(h.events("click").length, 0);
  h.gestures.destroy();
});

test("pan momentum covers the same distance in the same time at 60 Hz and 120 Hz", () => {
  function travel(frameMs: number) {
    const h = setup({pan: {x: true, y: true}});
    h.down(1, 100, 200); h.down(2, 200, 200);
    h.move(1, 130, 200); h.move(2, 230, 200); h.env.frame();
    h.up(1, 130, 200); h.up(2, 230, 200);
    let duration = 0;
    for (let i = 0; i < 500 && h.env.pendingFrames(); i++) { h.env.frame(frameMs); duration += frameMs; }
    const total = h.events("pan").reduce((sum, values) => sum + Number(values[0]), 0);
    h.gestures.destroy(); return {total, duration};
  }
  const sixty = travel(1000 / 60), oneTwenty = travel(1000 / 120);
  assert.ok(sixty.total > 100);
  assert.ok(Math.abs(sixty.total - oneTwenty.total) / sixty.total < 0.02);
  assert.ok(Math.abs(sixty.duration - oneTwenty.duration) <= 17,
    `glide duration differs: ${sixty.duration} ms vs ${oneTwenty.duration} ms`);
});


test("embedded-cursor trackpad coalesces real relative motion without a synthetic warp", () => {
  const h = setup({mode: "trackpad", relative: true});
  h.down(1, 100, 200); h.move(1, 130, 210); h.move(1, 150, 220); h.up(1, 150, 220);
  assert.deepEqual(h.events("relative"), [[85,34]]);
  assert.equal(h.events("move").length, 0);
  h.tap(100,200); h.env.advance(60); h.tap(100,200);
  assert.equal(h.events("click").length,2);
  assert.equal(h.events("move").length,0,"double tap cannot warp a real cursor");
  h.down(1,100,200); h.move(1,150,200); h.gestures.cancelAll(); h.env.frame();
  assert.equal(h.events("relative").length,1,"cancel discards queued relative motion");
  h.gestures.destroy();
});
