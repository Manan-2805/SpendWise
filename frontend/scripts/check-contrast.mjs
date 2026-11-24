import { readFileSync } from 'node:fs';

const css = readFileSync(new URL('../src/styles.css', import.meta.url), 'utf8');
const roles = { ink: 4.5, muted: 4.5, income: 4.5, expense: 4.5, warning: 4.5, focus: 3 };
const rows = [];
let failed = false;

function luminance([lightness, chroma, hue], name) {
  const radians = hue * Math.PI / 180;
  const a = chroma * Math.cos(radians);
  const b = chroma * Math.sin(radians);
  const l = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3;
  const m = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3;
  const s = (lightness - 0.0894841775 * a - 1.2914855480 * b) ** 3;
  const red = 4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s;
  const green = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s;
  const blue = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s;

  if ([red, green, blue].some((channel) => channel < 0 || channel > 1)) {
    throw new Error(`${name} is outside sRGB. Adjust the token before measuring it.`);
  }
  return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
}

function contrast(first, second) {
  return (Math.max(first, second) + 0.05) / (Math.min(first, second) + 0.05);
}

for (const [theme, selector] of [['light', ':root'], ['dark', ':root.dark']]) {
  const tokens = css.split(`${selector} {`)[1]?.split('}')[0];
  const values = Object.fromEntries(
    [...(tokens ?? '').matchAll(/--([a-z]+): oklch\(([\d.]+) ([\d.]+) ([\d.]+)\);/g)]
      .map(([, token, ...lch]) => [token, luminance(lch.map(Number), `${theme}/${token}`)]),
  );
  for (const surface of ['canvas', 'surface']) {
    const row = { theme, surface };
    for (const [role, minimum] of Object.entries(roles)) {
      const ratio = contrast(values[surface], values[role]);
      const passes = ratio >= minimum;
      row[role] = `${ratio.toFixed(2)}${passes ? '' : ' FAIL'}`;
      failed ||= !passes;
    }
    rows.push(row);
  }
}

console.table(rows);
if (failed) process.exitCode = 1;
