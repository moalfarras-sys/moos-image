// Export the native Mawj mark to the phone, browser and Windows tray.
import sharp from "sharp";
import pngToIco from "png-to-ico";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { copyFile, mkdir, writeFile } from "node:fs/promises";

const repo = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const logo = resolve(repo, "Logo.png");
const icons = resolve(repo, "controller/public/icons");
await mkdir(icons, { recursive: true });

for (const name of ["brand-logo.png", "icon-512.png"]) {
  await copyFile(logo, resolve(icons, name));
}
for (const [name, size] of [["icon-192.png", 192], ["favicon-64.png", 64]]) {
  await sharp(logo).resize(size, size).png().toFile(resolve(icons, name));
}

// The crest already sits inside the maskable central circle. Fill transparent
// margins for operating systems that supply their own icon silhouette.
for (const [name, size] of [["apple-touch-icon.png", 180], ["maskable-512.png", 512]]) {
  await sharp(logo).resize(size, size).flatten({ background: "#14191c" })
    .png().toFile(resolve(icons, name));
}

const frames = await Promise.all([16, 32, 48, 64, 128, 256].map(
  size => sharp(logo).resize(size, size).png().toBuffer(),
));
await writeFile(resolve(repo, "agent/app.ico"), await pngToIco(frames));
