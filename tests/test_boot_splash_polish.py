#!/usr/bin/env python3
"""Gates for the MoOS Plymouth boot splash.

WHAT THESE ARE FOR
    The splash is the one surface whose failure is invisible to every other
    check in this repo. `Theme=moos` can be set, the theme directory can be
    installed, the script can be in the initramfs — and the user can still get a
    grey text console, because Plymouth's script plugin falls back to text the
    moment it cannot load something the script asks for.

    So these gate the things that actually break it in practice:
      * a UTF-8 BOM, which makes Plymouth's parser reject the whole script —
        and plugin.c ignores that failure and reports success, so the user
        gets a pure black screen (no text fallback on Fedora 44),
      * the script asking for a file that is not there, and
      * the script doing unbounded work on every refresh.

    They deliberately do NOT gate the artistic content. The previous version of
    this file asserted on specific variable names from the sprite-based reveal
    (`logo_settled`, `field_settled`, `pulse_done`) and on an exact count of
    `logo_image.Scale` calls. All of that described one implementation rather
    than any property of a working splash, and all of it went stale the moment
    the theme became a frame sequence.
"""

from __future__ import annotations

import re
import json
import shutil
import subprocess
import struct
import importlib.util
import hashlib
import unittest
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

ROOT = Path(__file__).resolve().parents[1]
THEME = ROOT / "system_files/usr/share/plymouth/themes/moos"
SCRIPT = THEME / "moos.script"
BACKDROP = THEME / "boot-backdrop.png"
LOGIN_SCENE = (
    ROOT
    / "system_files/usr/share/wallpapers/MoOSUI2Graphite/contents/images_dark/3840x2160.jpg"
)


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()[:24]
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise AssertionError(f"not a PNG with an IHDR header: {path}")
    return struct.unpack(">II", data[16:24])


def script_text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def loaded_assets() -> list[str]:
    return sorted(set(re.findall(r'Image\("([^"]+)"\)', script_text())))


def scalar(name: str) -> float:
    m = re.search(rf"^\s*{name}\s*=\s*(-?[0-9]*\.?[0-9]+)\s*;", script_text(), re.MULTILINE)
    if not m:
        raise AssertionError(f"moos.script no longer defines {name}")
    return float(m.group(1))


def js_source() -> str:
    """moos.script as JavaScript for the callback harnesses.

    Plymouth creates an indexed array on first assignment; JavaScript needs a
    declaration. The arithmetic and control flow are otherwise identical.
    """
    text = script_text()
    arrays = sorted(set(re.findall(r"^\s*(\w+)\[[^\]]+\]\s*=", text, re.MULTILINE)))
    declarations = "".join(f"var {name} = [];\n" for name in arrays)
    return declarations + re.sub(r"\bfun\s+", "function ", text)


def intro_frames() -> list[Path]:
    fs = list(THEME.glob("intro*.png"))
    return sorted(fs, key=lambda p: int("".join(c for c in p.stem if c.isdigit())))


class BootSplashTests(unittest.TestCase):
    # ── the failure that produces a BLACK screen, not even text ────────────
    def test_script_has_no_utf8_bom(self) -> None:
        # A UTF-8 BOM (EF BB BF) at byte 0 makes Plymouth's scanner emit three
        # SYMBOL tokens before the first comment. The parser then rejects the
        # whole file ("Unparsed characters at end of file", L:1 C:0) and
        # script_parse_file() returns NULL — which plugin.c does NOT check: it
        # calls start_script_animation() anyway and reports success. plymouthd
        # therefore runs a theme that draws nothing (not even its background,
        # which this script sets), shows a pure black screen for the whole
        # splash window, and no gate on file presence can see it. Proven on
        # 2026-08-24 with the real Fedora 44 parser (plymouth 24.004.60):
        # with BOM -> PARSE FAILED; identical bytes minus BOM -> PARSE OK.
        raw = SCRIPT.read_bytes()
        self.assertFalse(raw.startswith(b"\xef\xbb\xbf"),
                         "moos.script starts with a UTF-8 BOM: Plymouth's parser "
                         "rejects the entire theme and boots a black splash "
                         "(plugin.c ignores the NULL parse result)")

    def test_theme_ships_no_bom_in_any_asset(self) -> None:
        for path in sorted(THEME.iterdir()):
            if not path.is_file():
                continue
            with self.subTest(asset=path.name):
                self.assertFalse(path.read_bytes()[:3] == b"\xef\xbb\xbf",
                                 f"{path.name} starts with a UTF-8 BOM")

    # ── the failure that produces a text console ────────────────────────────
    def test_every_image_the_script_loads_is_installed(self) -> None:
        assets = loaded_assets()
        self.assertTrue(assets, "moos.script loads no images at all")
        for name in assets:
            with self.subTest(asset=name):
                self.assertTrue((THEME / name).is_file(),
                                f"moos.script loads {name}, which is not in the theme — "
                                f"Plymouth would abort this splash to its text fallback")

    def test_boot_identity_is_fixed_and_independent_of_the_login_scene(self) -> None:
        self.assertEqual(png_size(BACKDROP), (1920, 1080))
        generator = ROOT / "artwork/generate_boot_backdrop.py"
        spec = importlib.util.spec_from_file_location("boot_art", generator)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with Image.open(BACKDROP) as actual:
            expected = module.make_backdrop()
            actual_rgb = actual.convert("RGB")
            difference = ImageChops.difference(expected, actual_rgb)
            self.assertIsNone(
                difference.getbbox(),
                "boot-backdrop.png drifted from the fixed MoOS boot identity; "
                "regenerate it with artwork/generate_boot_backdrop.py",
            )
        # Preserve the original coupled implementation as a failing control.
        with Image.open(LOGIN_SCENE) as old:
            self.assertIsNotNone(ImageChops.difference(
                actual_rgb, old.convert("RGB").resize((1920, 1080), Image.Resampling.LANCZOS)).getbbox())
        self.assertNotIn("/wallpapers/", generator.read_text())
        self.assertNotIn("kdeglobals", generator.read_text())
        self.assertLess(
            BACKDROP.stat().st_size / 1048576,
            4,
            "the boot backdrop adds more than 4 MiB to every initramfs",
        )
        luminance = actual_rgb.convert("L")
        self.assertGreater(
            ImageStat.Stat(luminance).mean[0],
            10,
            "the boot backdrop regressed to a black-looking screen",
        )
        low, high = luminance.getextrema()
        self.assertGreaterEqual(
            high - low,
            15,
            "the boot backdrop lost the visible depth required by the visual gate",
        )

    def test_arabic_greeting_is_shaped_and_preserves_prompt_space(self) -> None:
        provenance = json.loads((ROOT / "artwork/moos-design/boot-caption.json").read_text())
        self.assertEqual(provenance["caption"], "مرحبًا بك")
        self.assertEqual(provenance["captions"]["farewell"]["caption"], "إلى اللقاء")
        font = ROOT / provenance["fontSource"]
        self.assertEqual(hashlib.sha256(font.read_bytes()).hexdigest(), provenance["fontSHA256"])
        for key, name in (("welcome", "welcome-ar.png"), ("farewell", "farewell-ar.png")):
            record = provenance["captions"][key]
            with Image.open(THEME / name) as caption:
                self.assertEqual(list(caption.size), record["size"])
                self.assertEqual(hashlib.sha256(caption.tobytes()).hexdigest(), record["pixelSHA256"])
                self.assertEqual(caption.mode, "RGBA")
                box = caption.getbbox()
                self.assertIsNotNone(box)
                # Stacked marks (tanween, hamza below alef) keep a clear margin.
                self.assertGreater(box[1], 0)
                self.assertLess(box[3], caption.height)
                self.assertLess((THEME / name).stat().st_size, 65536)
        self.assertIn('greeting_sprite.SetOpacity(0)', script_text())

    def test_backdrop_is_scaled_once_outside_the_refresh_loop(self) -> None:
        text = script_text()
        setup, refresh = text.split("fun refresh()", 1)
        self.assertIn('Image("boot-backdrop.png").Scale(', setup)
        self.assertNotIn("boot-backdrop.png", refresh)
        self.assertIn(
            "backdrop_scale = fmax(sw / BACKDROP_W, sh / BACKDROP_H)", setup
        )
        self.assertIn("backdrop_sprite.SetX(cx - backdrop_w / 2)", setup)
        self.assertIn("backdrop_sprite.SetY(cy - backdrop_h / 2)", setup)

    def test_intro_count_matches_the_frames_on_disk(self) -> None:
        self.assertEqual(int(scalar("INTRO_COUNT")), len(intro_frames()),
                         "INTRO_COUNT and the installed intro frames disagree: either the "
                         "tail of the animation never plays, or the script loads a file "
                         "that is not there")

    def test_frame_filenames_are_literal_not_built_by_concatenation(self) -> None:
        # Plymouth's script language has no string formatting and its
        # number-to-string conversion is not specified to yield "1" rather than
        # "1.000000". A filename built by concatenation can therefore resolve to
        # nothing on some Plymouth build, and the whole splash drops to text —
        # on a user's machine, never here.
        self.assertNotRegex(script_text(), r'Image\(\s*"[^"]*"\s*\+',
                            "an Image() filename is being built by concatenation")

    # ── the failure that makes boot slow or memory-hungry ──────────────────
    def test_refresh_scales_at_most_one_image(self) -> None:
        body = script_text().split("fun refresh()", 1)
        self.assertEqual(len(body), 2, "moos.script has no refresh() function")
        refresh = body[1].split("\nPlymouth.SetRefreshFunction", 1)[0]
        self.assertLessEqual(refresh.count(".Scale("), 1,
                             "refresh() scales more than one image per call; at 50 Hz on a "
                             "cold boot that is the splash competing with the boot it is "
                             "supposed to be covering")

    def test_frames_are_not_prescaled_into_memory(self) -> None:
        # Pre-scaling the whole sequence at load time costs frames x screen x 4
        # bytes inside the initramfs — ~219 MiB at 1080p for 32 frames, on
        # machines that may have 1 GB.
        setup = script_text().split("fun refresh()", 1)[0]
        self.assertNotRegex(setup, r"frames\[\s*i\s*\]\s*=\s*Image\([^)]*\)\.Scale",
                            "the intro sequence is being scaled at load time")

    def test_intro_frames_fit_the_initramfs_budget(self) -> None:
        frames = intro_frames()
        self.assertTrue(frames, "no intro frames installed")
        w, h = png_size(frames[0])
        decoded_mib = len(frames) * w * h * 4 / 1048576
        # The sequence is stored at the render's own crop width rather than
        # downscaled, because the splash now rests on its last frame and that
        # frame is what the user looks at longest. That buys sharpness and costs
        # RAM inside the initramfs; this is where the trade is pinned.
        self.assertLess(decoded_mib, 4,
                        f"the intro sequence decodes to {decoded_mib:.0f} MiB in the "
                        f"initramfs; that is charged to every boot on every machine")
        on_disk_mib = sum(p.stat().st_size for p in frames) / 1048576
        self.assertLess(on_disk_mib, 1,
                        f"the intro sequence is {on_disk_mib:.1f} MiB on disk and is copied "
                        f"into the initramfs")

    # ── the failure that shows a stretched or frozen frame ─────────────────
    def test_the_script_declares_the_aspect_its_frames_actually_have(self) -> None:
        fw, fh = png_size(intro_frames()[0])
        self.assertAlmostEqual(scalar("INTRO_ASPECT"), fw / fh, delta=0.005,
                               msg="INTRO_ASPECT does not match the frames, so the sequence "
                                   "is drawn stretched")

    def test_quit_leaves_a_composed_frame_not_a_frozen_one(self) -> None:
        text = script_text()
        self.assertIn("Plymouth.SetQuitFunction", text,
                      "no quit handler: `plymouth quit --retain-splash` would leave whatever "
                      "mid-animation frame happened to be showing on screen for the whole "
                      "login-manager bring-up")
        quit_body = text.split("fun quit_callback()", 1)[1].split("}", 1)[0]
        # It must PIN the last frame, not leave whatever was mid-flight.
        self.assertIn("intro_sprite.SetImage(hero)", quit_body,
                      "quit does not jump to the sequence's resting frame")
        self.assertIn("intro_sprite.SetOpacity(1)", quit_body)
        self.assertIn("finished = 1", quit_body)
        self.assertNotIn(".Scale(", quit_body)

    def test_entrance_finishes_without_perpetual_motion(self) -> None:
        text = script_text()
        refresh = text.split("fun refresh()", 1)[1].split("Plymouth.SetRefreshFunction", 1)[0]
        self.assertNotIn(".Scale(", refresh)
        # A short scene, never a loop: at 25 Hz this is at most two seconds.
        self.assertLessEqual(scalar("ENTRANCE_TICKS"), 50)
        self.assertIn("tick >= ENTRANCE_TICKS", refresh)
        self.assertIn("finished = 1", refresh)
        self.assertEqual(len(intro_frames()), 1)

    @unittest.skipUnless(shutil.which('node'), 'callback evaluation needs Node')
    def test_arrival_settles_and_early_handoff_never_keeps_an_offset(self) -> None:
        # Evaluate the actual callback arithmetic, without pretending these
        # recording APIs are native Plymouth or pixels. The native script
        # parser and final-initramfs/boot gates remain separate requirements.
        prelude = '''
const vm = require('node:vm');
function check(source, mode) {
  const calls = []; let scaled = 0;
  function picture(w=853,h=554) { return {GetWidth:()=>w,GetHeight:()=>h,
    Scale:(x,y)=>{scaled++;return picture(x,y);}}; }
  const Image = () => picture(); Image.Text = () => picture(100,20);
  const context = {frames:[], Image, Sprite:()=>({x:0,y:0,opacity:1,
    SetImage(image){this.image=image;calls.push(['image',image]);},SetX(x){this.x=x;},SetZ:()=>{},
    SetY(y){this.y=y;calls.push(['y',y]);},
    SetOpacity(a){this.opacity=a;calls.push(['alpha',a]);}}),
    Window:{GetWidth:()=>1536,GetHeight:()=>864,SetBackgroundTopColor:()=>{},SetBackgroundBottomColor:()=>{}},
    Math:{Cos:Math.cos,Sin:Math.sin},
    Plymouth:{GetMode:()=>mode,SetRefreshRate:()=>{},
      SetRefreshFunction:f=>context.refreshCallback=f,SetQuitFunction:f=>context.quitCallback=f,
      SetMessageFunction:()=>{},SetDisplayPasswordFunction:()=>{},SetDisplayNormalFunction:()=>{}}};
  vm.runInNewContext(source,context,{timeout:1000});
  const initialScaleCount=scaled;
  if (mode==='boot' || mode==='boot-full') {
    if (!(context.intro_sprite.y>context.stage_y)) throw Error('missing finite arrival');
    if (mode==='boot-full') {
      if (!(context.intro_sprite.opacity>=context.MARK_GHOST && context.MARK_GHOST>0))
        throw Error('the mark is absent from the first frame');
      for(let i=0;i<8;i++) context.refreshCallback();
      if (!(context.greeting_sprite.opacity===0 &&
            context.drop_sprite.some(d=>d.opacity>0)))
        throw Error('the droplets did not flow before the greeting');
      for(let i=8;i<38;i++) context.refreshCallback();
      if (!(context.intro_sprite.opacity===1 && context.greeting_sprite.opacity>0 &&
            context.greeting_sprite.opacity<1)) throw Error('missing greeting arrival');
      for(let i=38;i<context.ENTRANCE_TICKS;i++) context.refreshCallback();
      if(context.letter_sprite.some((letter,k)=>letter.image!==context.letter_image[k]))
        throw Error('wordmark kept its last blended pixels');
    } else {
      context.refreshCallback(); context.refreshCallback(); context.refreshCallback();
      context.quitCallback();
    }
    if (Math.abs(context.intro_sprite.y-context.stage_y)>0.01 || context.intro_sprite.opacity!==1)
      throw Error('handoff kept the in-flight offset');
  } else if (context.intro_sprite.y!==context.stage_y || context.intro_sprite.opacity!==1) {
    throw Error('shutdown did not start at rest');
  }
  const greetingOpacity=(mode==='shutdown'||mode==='reboot')?0:1;
  if(context.greeting_sprite.opacity!==greetingOpacity || context.greeting_sprite.y!==context.greeting_y)
    throw Error('greeting did not settle at handoff');
  if(context.farewell_sprite.opacity!==1-greetingOpacity)
    throw Error('farewell does not match the mode');
  if(context.drop_sprite.some(d=>d.opacity!==0) || context.glint_sprite.opacity!==0)
    throw Error('a droplet or glint stayed on the resting frame');
  if(context.bezel_sprite.opacity!==1 || context.sheen_sprite.opacity!==context.SHEEN_REST ||
     context.sheen_sprite.y!==context.sheen_y || context.letter_sprite.some((l,k)=>
       l.opacity!==1 || l.y!==context.word_y))
    throw Error('glass or wordmark did not settle');
  const settled=calls.length;
  for(let i=0;i<200;i++) context.refreshCallback();
  if (calls.length!==settled || scaled!==initialScaleCount) throw Error('rest keeps doing work');
  return true;
}
'''
        source = js_source()
        for line, refusal in (
            (None, None),
            ('    intro_sprite.SetY(stage_y);\n', 'handoff kept the in-flight offset'),
            ('                letter_sprite[k].SetImage(letter_image[k]);\n', 'wordmark kept its last blended pixels'),
        ):
            candidate = source
            if line:
                self.assertEqual(candidate.count(line), 1)
                candidate = candidate.replace(line, '', 1)
            program = prelude+'\nconst source='+json.dumps(candidate)+';\n'
            program += "check(source,'boot');check(source,'boot-full');check(source,'shutdown');check(source,'reboot');process.stdout.write('MOOS_BOOT_CALLBACK_PASS');"
            p = subprocess.run([shutil.which('node'), '-e', program], capture_output=True, text=True, timeout=10)
            if refusal:
                self.assertNotEqual(p.returncode, 0)
                self.assertIn(refusal, p.stderr)
            else:
                self.assertEqual(p.returncode, 0, p.stdout+p.stderr)
                self.assertIn('MOOS_BOOT_CALLBACK_PASS', p.stdout)

    @unittest.skipUnless(shutil.which('node'), 'callback evaluation needs Node')
    def test_password_rows_use_native_line_room_and_stay_on_screen(self) -> None:
        # Native current Plymouth/Pango with the actual Meyar bytes measured
        # Latin 169x23, Arabic 234x37, and four password bullets 36x23.
        # The old 80%/85% placement overpainted Arabic ink by 33 pixels at
        # 640x360 and five at 640x480. Evaluate the actual script callbacks;
        # native rendered ink controls remain the independent pixel evidence.
        prelude = r'''const vm = require('node:vm');
function check(source) {
  for (const [w,h] of [[640,360],[800,480],[640,480],[360,640],[1920,1080]]) {
    function picture(width,height) { return {GetWidth:()=>width,GetHeight:()=>height,
      Scale:(x,y)=>picture(x,y)}; }
    const Image = name => name==='welcome-ar.png' ? picture(287,94) : picture(856,556);
    Image.Text = text => text==='Arabic' ? picture(234,37) :
      text==='long' ? picture(1500,37) : text==='Latin' ? picture(169,23) :
      picture(text.trim().length*9 || 4,23);
    const context = {frames:[], Image, Sprite:()=>({x:0,y:0,opacity:1,image:null,
      SetImage(image){this.image=image;},SetX(x){this.x=x;},SetY(y){this.y=y;},
      SetZ:()=>{},SetOpacity(a){this.opacity=a;}}),
      Window:{GetWidth:()=>w,GetHeight:()=>h,SetBackgroundTopColor:()=>{},SetBackgroundBottomColor:()=>{}},
      Plymouth:{GetMode:()=>'boot',SetRefreshRate:()=>{},SetRefreshFunction:()=>{},
        SetQuitFunction:()=>{},SetMessageFunction:()=>{},SetDisplayPasswordFunction:()=>{},
        SetDisplayNormalFunction:()=>{}}};
    vm.runInNewContext(source,context,{timeout:1000});
    for(const text of ['Arabic','Latin','long']) for(const count of [0,1,4,120]) {
      context.display_password(text,count);
      const p=context.prompt_sprite,b=context.bullets_sprite;
      if (b.y < p.y+p.image.GetHeight()+Math.min(8,h*.02)-.01)
        throw Error('password row overlaps native prompt line');
      if (p.y<0 || b.y+b.image.GetHeight()>h-Math.min(12,h*.025)+.01)
        throw Error('password rows exceed screen');
      if (p.x<0 || b.x<0 || p.x+p.image.GetWidth()>w || b.x+b.image.GetWidth()>w)
        throw Error('password rows exceed width');
      if (context.intro_sprite.y!==context.stage_y || context.intro_sprite.opacity!==1)
        throw Error('password did not settle the hero');
    }
    context.display_normal();
    if(context.prompt_sprite.opacity!==0 || context.bullets_sprite.opacity!==0)
      throw Error('normal display retained password rows');
  }
}
'''
        source = js_source()
        for old in (False, True):
            candidate = source
            if old:
                candidate = candidate.replace('prompt_sprite.SetY(prompt_y);',
                                               'prompt_sprite.SetY(sh * 0.80);')
                candidate = candidate.replace('bullets_sprite.SetY(bullets_y);',
                                               'bullets_sprite.SetY(sh * 0.85);')
            program = prelude + '\ncheck(' + json.dumps(candidate) + ");process.stdout.write('MOOS_PASSWORD_ROWS_PASS');"
            result = subprocess.run([shutil.which('node'), '-e', program],
                                    capture_output=True, text=True, timeout=10)
            if old:
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('password row overlaps native prompt line', result.stderr)
            else:
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('MOOS_PASSWORD_ROWS_PASS', result.stdout)

    # ── the Liquid Glass composition ───────────────────────────────────────
    def test_glass_layers_fit_their_decode_and_initramfs_budget(self) -> None:
        # Every image the script loads except the fixed 1080p backdrop: the
        # improved mark, two lens layers, droplets, glint, letters, captions.
        names = [n for n in loaded_assets() if n != "boot-backdrop.png"]
        decoded = on_disk = 0
        for name in names:
            w, h = png_size(THEME / name)
            decoded += w * h * 4
            on_disk += (THEME / name).stat().st_size
        self.assertLess(decoded / 1048576, 6,
                        f"the glass layers decode to {decoded / 1048576:.1f} MiB in the initramfs")
        self.assertLess(on_disk / 1048576, 1.5,
                        f"the glass layers add {on_disk / 1048576:.2f} MiB to every initramfs")

    def test_glass_assets_come_from_the_recorded_blender_build(self) -> None:
        record = json.loads((ROOT / "artwork/moos-design/boot-glass.json").read_text())
        svg = ROOT / "artwork/logo/MoOS_Logo_Vector_High_Detail.svg"
        self.assertEqual(hashlib.sha256(svg.read_bytes()).hexdigest(), record["logo"]["svgSHA256"],
                         "the boot mark is no longer derived from the owner's vector master")
        scene = ROOT / record["scene"]
        self.assertEqual(hashlib.sha256(scene.read_bytes()).hexdigest(), record["sceneSHA256"])
        self.assertTrue(record["renderer"].startswith("Blender "))
        for name in loaded_assets():
            with self.subTest(asset=name):
                self.assertEqual(hashlib.sha256((THEME / name).read_bytes()).hexdigest(),
                                 record["assets"][name]["sha256"],
                                 f"{name} differs from artwork/generate_boot_glass.py output")

    @unittest.skipUnless(shutil.which('node'), 'layout evaluation needs Node')
    def test_resting_composition_fits_every_screen_and_leaves_prompt_room(self) -> None:
        # Execute the actual setup arithmetic with the shipped image sizes.
        sizes = {name: list(png_size(THEME / name)) for name in loaded_assets()}
        prelude = r'''const vm = require('node:vm');
function layout(source, sizes, w, h, mode) {
  const sprites = [];
  function picture(width,height) { return {GetWidth:()=>width,GetHeight:()=>height,
    Scale:(x,y)=>picture(x,y)}; }
  const Image = name => picture(...sizes[name]);
  Image.Text = () => picture(100,20);
  const context = {Image, Sprite:(image)=>{const s={x:0,y:0,opacity:1,image,
      SetImage(i){this.image=i;},SetX(x){this.x=x;},SetY(y){this.y=y;},SetZ(){},
      SetOpacity(a){this.opacity=a;}}; sprites.push(s); return s;},
    Math:{Cos:Math.cos,Sin:Math.sin},
    Window:{GetWidth:()=>w,GetHeight:()=>h,SetBackgroundTopColor:()=>{},SetBackgroundBottomColor:()=>{}},
    Plymouth:{GetMode:()=>mode,SetRefreshRate:()=>{},SetRefreshFunction:f=>context.refresh=f,
      SetQuitFunction:f=>context.quit=f,SetMessageFunction:()=>{},SetDisplayPasswordFunction:()=>{},
      SetDisplayNormalFunction:()=>{}}};
  vm.runInNewContext(source, context, {timeout:1000});
  context.quit();
  const box = s => [s.x, s.y, s.x + s.image.GetWidth(), s.y + s.image.GetHeight()];
  const c = context, fail = m => { throw Error(`${w}x${h} ${mode}: ${m}`); };
  const shown = sprites.filter(s => s.image && s.opacity > 0 && s !== c.backdrop_sprite);
  for (const s of shown) { const [x0,y0,x1,y1] = box(s);
    if (x0 < 0 || y0 < 0 || x1 > w || y1 > h) fail('a resting layer leaves the screen'); }
  const lens = box(c.bezel_sprite), letters = c.letter_sprite.map(box);
  if (letters[0][1] < lens[1] + (lens[3]-lens[1]) * 0.89) fail('the wordmark overlaps the glass ring');
  for (let k = 1; k < 4; k++) if (letters[k][0] < letters[k-1][0]) fail('letters out of order');
  const ink = (k) => [letters[k][0] + c.letter_pad, letters[k][2] - c.letter_pad];
  for (let k = 1; k < 4; k++) if (ink(k)[0] < ink(k-1)[1] - 0.01) fail('letters overlap');
  const caption = mode === 'boot' ? c.greeting_sprite : c.farewell_sprite;
  const cap = box(caption);
  if (cap[1] < letters[0][3]) fail('the Arabic caption overlaps the wordmark');
  if (cap[3] > h * 0.80) fail('the Arabic caption enters the passphrase rows');
  if (Math.abs((letters[0][0] + letters[3][2]) / 2 - w / 2) > 1) fail('wordmark not centred');
}
'''
        source = js_source()
        for broken in (False, True):
            candidate = source
            if broken:
                # Original control: drop the tracking compensation for the
                # letters' transparent margins and the word drifts off centre.
                line = "word_w = word_w + 3 * (tracking - 2 * letter_pad);"
                self.assertEqual(candidate.count(line), 1)
                candidate = candidate.replace(line, "word_w = word_w + 3 * tracking;")
            program = prelude + "const sizes=" + json.dumps(sizes) + ";const source=" + json.dumps(candidate) + ";"
            program += ("for (const [w,h] of [[640,480],[360,640],[800,1280],[1920,1080],[2560,1600],"
                        "[3840,2160],[3440,1440]]) for (const m of ['boot','shutdown']) layout(source,sizes,w,h,m);"
                        "process.stdout.write('MOOS_GLASS_LAYOUT_PASS');")
            result = subprocess.run([shutil.which('node'), '-e', program], capture_output=True,
                                    text=True, timeout=20)
            if broken:
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('wordmark not centred', result.stderr)
            else:
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('MOOS_GLASS_LAYOUT_PASS', result.stdout)

    def test_the_fallback_ground_is_the_fixed_boot_canvas(self) -> None:
        # Boot belongs to the OS identity, independently of a user's theme.
        text = script_text()
        for fn in ("SetBackgroundTopColor", "SetBackgroundBottomColor"):
            self.assertIn(f"Window.{fn}(0.039, 0.063, 0.106)", text,
                          f"{fn} is not the fixed #0A101B boot ground")

    def test_boot_text_overlays_are_screen_bounded(self) -> None:
        # Plymouth messages can be long: fsck paths, recovery notices, device
        # waits, or encrypted-volume prompts. If they are centered at natural
        # width, small screens and VMs clip them off both edges during the boot
        # moment where the user has the least context. Scale those event-driven
        # text images to the screen, but keep refresh() cheap.
        text = script_text()
        self.assertIn("OVERLAY_MAX_W = sw * 0.78;", text)
        for marker, image_var in (
            ("fun message_callback(text)", "img"),
            ("fun display_password(prompt, bullets)", "pimg"),
            ("fun display_password(prompt, bullets)", "bimg"),
        ):
            with self.subTest(marker=marker, image=image_var):
                end_marker = (
                    "fun hide_message()"
                    if marker == "fun message_callback(text)"
                    else "fun clear_password()"
                )
                body = text.split(marker, 1)[1].split(end_marker, 1)[0]
                self.assertIn(f"{image_var}.GetWidth() > OVERLAY_MAX_W", body)
                self.assertIn(
                    f"{image_var}.Scale(OVERLAY_MAX_W, "
                    f"{image_var}.GetHeight() * OVERLAY_MAX_W / {image_var}.GetWidth())",
                    body,
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
