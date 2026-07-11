// Generates premium app/PWA icons from the repo-root Logo.png.
//   controller/public/icons/*   -> PWA + Apple icons + login logo
//   agent/app.ico               -> Windows .exe + tray icon
// Run from the controller/ directory:  npm run gen-icons
import sharp from "sharp";
import pngToIco from "png-to-ico";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { mkdir, writeFile } from "node:fs/promises";

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(here, "..", "..");
const logo = resolve(repoRoot, "Logo.png");
const iconsDir = resolve(repoRoot, "controller", "public", "icons");
const agentDir = resolve(repoRoot, "agent");

// Knock out the near-white background so only the coloured "Mo" mark remains.
async function cutoutBuffer() {
  const { data, info } = await sharp(logo).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
  for (let i = 0; i < data.length; i += 4) {
    const r = data[i], g = data[i + 1], b = data[i + 2];
    if (Math.min(r, g, b) > 226) data[i + 3] = 0;
  }
  return sharp(data, { raw: { width: info.width, height: info.height, channels: 4 } }).png().toBuffer();
}

// Premium icon: deep gradient + soft glow + the cutout mark, centred.
function bgSvg(size) {
  return `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="#2b3768"/>
        <stop offset="0.52" stop-color="#161d3a"/>
        <stop offset="1" stop-color="#090d1a"/>
      </linearGradient>
      <radialGradient id="glow" cx="50%" cy="50%" r="40%">
        <stop offset="0" stop-color="#ffffff" stop-opacity="0.95"/>
        <stop offset="46%" stop-color="#aebcff" stop-opacity="0.32"/>
        <stop offset="100%" stop-color="#ffffff" stop-opacity="0"/>
      </radialGradient>
      <radialGradient id="topshine" cx="50%" cy="14%" r="60%">
        <stop offset="0" stop-color="#ffffff" stop-opacity="0.12"/>
        <stop offset="100%" stop-color="#ffffff" stop-opacity="0"/>
      </radialGradient>
    </defs>
    <rect width="${size}" height="${size}" fill="url(#g)"/>
    <rect width="${size}" height="${size}" fill="url(#topshine)"/>
    <circle cx="${size / 2}" cy="${size / 2}" r="${size * 0.36}" fill="url(#glow)"/>
  </svg>`;
}

// Rounded-square alpha mask (squircle-ish) so the icon reads as a modern app tile.
function roundMask(size, radiusFrac = 0.22) {
  const r = Math.round(size * radiusFrac);
  return Buffer.from(
    `<svg width="${size}" height="${size}" xmlns="http://www.w3.org/2000/svg"><rect x="0" y="0" width="${size}" height="${size}" rx="${r}" ry="${r}"/></svg>`
  );
}

async function premiumIcon(size, logoFrac = 0.54, { rounded = true } = {}) {
  const bg = await sharp(Buffer.from(bgSvg(size))).png().toBuffer();
  const cut = await cutoutBuffer();
  const lw = Math.round(size * logoFrac);
  const logoImg = await sharp(cut).trim()
    .resize(lw, lw, { fit: "contain", background: { r: 0, g: 0, b: 0, alpha: 0 } }).toBuffer();
  let img = sharp(bg).composite([{ input: logoImg, gravity: "center" }]);
  if (rounded) {
    // clip to the rounded square (transparent corners) — clean in the taskbar & tray.
    img = sharp(await img.png().toBuffer()).composite([{ input: roundMask(size), blend: "dest-in" }]);
  }
  return img.png();
}

async function main() {
  await mkdir(iconsDir, { recursive: true });

  await (await premiumIcon(192)).toFile(resolve(iconsDir, "icon-192.png"));
  await (await premiumIcon(512)).toFile(resolve(iconsDir, "icon-512.png"));
  await (await premiumIcon(180)).toFile(resolve(iconsDir, "apple-touch-icon.png"));
  await (await premiumIcon(512, 0.42)).toFile(resolve(iconsDir, "maskable-512.png")); // extra safe-zone
  await (await premiumIcon(512, 0.6)).toFile(resolve(iconsDir, "brand-logo.png"));    // login screen
  await (await premiumIcon(64)).toFile(resolve(iconsDir, "favicon-64.png"));

  // Windows .ico for the agent (.exe + tray + taskbar), multi-size. Smaller frames use a
  // bigger mark so it stays legible at 16–32px instead of shrinking into a dark blob.
  const icoSpec = [
    { s: 16, frac: 0.86 }, { s: 24, frac: 0.84 }, { s: 32, frac: 0.82 },
    { s: 48, frac: 0.78 }, { s: 64, frac: 0.74 }, { s: 128, frac: 0.70 }, { s: 256, frac: 0.68 },
  ];
  const bufs = [];
  // Tiny frames (≤32px) keep square corners — rounding is invisible there and only eats pixels.
  for (const { s, frac } of icoSpec) bufs.push(await (await premiumIcon(s, frac, { rounded: s > 32 })).toBuffer());
  await writeFile(resolve(agentDir, "app.ico"), await pngToIco(bufs));

  console.log("Premium icons generated:");
  console.log("  ->", iconsDir);
  console.log("  ->", resolve(agentDir, "app.ico"));
}

main().catch((err) => { console.error("Icon generation failed:", err); process.exit(1); });
