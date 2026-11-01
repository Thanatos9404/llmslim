import sharp from "sharp";
const [web, brand] = process.argv.slice(2);
const icon = `${web}/public/brand/llmslim-app-icon.svg`;
const jobs = [
  [icon, 512, `${web}/src/app/icon.png`],
  [icon, 512, `${web}/public/icon-512.png`],
  [icon, 192, `${web}/public/icon-192.png`],
  [icon, 500, `${web}/public/favicon.png`],
  [icon, 500, `${web}/public/llmslim_logo.png`],
  [`${brand}/app-icon-bleed.svg`, 180, `${web}/src/app/apple-icon.png`],
  ...[16, 32, 48, 64, 256].map((s) => [icon, s, `${brand}/ico-${s}.png`]),
];
for (const [src, size, out] of jobs) await sharp(src, { density: 400 }).resize(size, size).png().toFile(out);
await sharp(`${brand}/og.svg`, { density: 96 }).resize(1200, 630).flatten({ background: "#060816" }).png({ compressionLevel: 9 }).toFile(`${web}/public/og.png`);
console.log("icons ok");
