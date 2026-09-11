import { deflateSync } from "node:zlib";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
mkdirSync(resolve(root, "public"), { recursive: true });
mkdirSync(resolve(root, "src-tauri/icons"), { recursive: true });

const crcTable = new Uint32Array(256);
for (let n = 0; n < 256; n += 1) {
  let value = n;
  for (let k = 0; k < 8; k += 1) value = value & 1 ? 0xedb88320 ^ (value >>> 1) : value >>> 1;
  crcTable[n] = value >>> 0;
}

function crc32(bytes) {
  let crc = 0xffffffff;
  for (const byte of bytes) crc = crcTable[(crc ^ byte) & 0xff] ^ (crc >>> 8);
  return (crc ^ 0xffffffff) >>> 0;
}

function chunk(type, data) {
  const name = Buffer.from(type);
  const length = Buffer.alloc(4);
  length.writeUInt32BE(data.length);
  const checksum = Buffer.alloc(4);
  checksum.writeUInt32BE(crc32(Buffer.concat([name, data])));
  return Buffer.concat([length, name, data, checksum]);
}

function makePng(size) {
  const raw = Buffer.alloc((size * 4 + 1) * size);
  const center = (size - 1) / 2;
  for (let y = 0; y < size; y += 1) {
    const row = y * (size * 4 + 1);
    for (let x = 0; x < size; x += 1) {
      const offset = row + 1 + x * 4;
      const dx = (x - center) / size;
      const dy = (y - center) / size;
      const body = Math.abs(dx) < 0.29 && Math.abs(dy) < 0.25;
      const round = dx * dx + dy * dy < 0.13;
      if (body || round) {
        raw[offset] = 217;
        raw[offset + 1] = 255;
        raw[offset + 2] = 95;
        raw[offset + 3] = 255;
      }
      const eye = Math.abs(dy) < 0.035 && (Math.abs(dx - 0.105) < 0.035 || Math.abs(dx + 0.105) < 0.035);
      if (eye) {
        raw[offset] = 23;
        raw[offset + 1] = 24;
        raw[offset + 2] = 20;
        raw[offset + 3] = 255;
      }
    }
  }
  const header = Buffer.alloc(13);
  header.writeUInt32BE(size, 0);
  header.writeUInt32BE(size, 4);
  header[8] = 8;
  header[9] = 6;
  const signature = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
  return Buffer.concat([signature, chunk("IHDR", header), chunk("IDAT", deflateSync(raw)), chunk("IEND", Buffer.alloc(0))]);
}

const palette = [
  [0, 0, 0],
  [217, 255, 95],
  [23, 24, 20],
  [245, 246, 238],
  [108, 128, 51],
  [255, 180, 75],
  [88, 91, 80],
  [198, 225, 109],
];

function framePixels(frame) {
  const width = 96;
  const pixels = new Uint8Array(width * width);
  const bounce = [3, 1, 0, 1, 3, 4, 3, 2][frame];
  const set = (x, y, color) => {
    if (x >= 0 && y >= 0 && x < width && y < width) pixels[y * width + x] = color;
  };
  const rect = (x, y, w, h, color) => {
    for (let py = y; py < y + h; py += 1) for (let px = x; px < x + w; px += 1) set(px, py, color);
  };
  const circle = (cx, cy, radius, color) => {
    for (let y = cy - radius; y <= cy + radius; y += 1) {
      for (let x = cx - radius; x <= cx + radius; x += 1) {
        if ((x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2) set(x, y, color);
      }
    }
  };
  const y = 20 + bounce;
  rect(46, y - 12, 4, 12, 4);
  circle(48, y - 14, 4, 5);
  circle(48, y + 30, 29, 4);
  rect(20, y + 18, 56, 32, 1);
  circle(25, y + 22, 8, 1);
  circle(71, y + 22, 8, 1);
  rect(25, y + 16, 46, 38, 1);
  rect(29, y + 23, 38, 21, 2);
  rect(32, y + 26, 32, 15, 3);
  const blink = frame === 3 || frame === 4;
  rect(37, y + (blink ? 33 : 29), 6, blink ? 2 : 7, 2);
  rect(53, y + (blink ? 33 : 29), 6, blink ? 2 : 7, 2);
  rect(43, y + 42, 10, 3, 4);
  rect(17, y + 31, 6, 17, 7);
  rect(73, y + 31, 6, 17, 7);
  rect(31, y + 52, 11, 9, 1);
  rect(54, y + 52, 11, 9, 1);
  return pixels;
}

function packCodes(codes, bits) {
  const output = [];
  let value = 0;
  let count = 0;
  for (const code of codes) {
    value |= code << count;
    count += bits;
    while (count >= 8) {
      output.push(value & 0xff);
      value >>>= 8;
      count -= 8;
    }
  }
  if (count) output.push(value & 0xff);
  return Buffer.from(output);
}

function gifFrame(pixels, delay) {
  const clear = 8;
  const end = 9;
  const codes = [];
  for (const pixel of pixels) codes.push(clear, pixel);
  codes.push(end);
  const compressed = packCodes(codes, 4);
  const blocks = [];
  for (let i = 0; i < compressed.length; i += 255) {
    const block = compressed.subarray(i, i + 255);
    blocks.push(Buffer.from([block.length]), block);
  }
  const graphicControl = Buffer.from([0x21, 0xf9, 0x04, 0x05, delay & 0xff, delay >> 8, 0x00, 0x00]);
  const descriptor = Buffer.from([0x2c, 0, 0, 0, 0, 96, 0, 96, 0, 0]);
  return Buffer.concat([graphicControl, descriptor, Buffer.from([3]), ...blocks, Buffer.from([0])]);
}

function makeGif(paletteList, pixelFn) {
  const header = Buffer.from("GIF89a", "ascii");
  const logicalScreen = Buffer.from([96, 0, 96, 0, 0xf2, 0, 0]);
  const colorTable = Buffer.from(paletteList.flat());
  const loop = Buffer.from([0x21, 0xff, 0x0b, ...Buffer.from("NETSCAPE2.0"), 0x03, 0x01, 0x00, 0x00, 0x00]);
  const frames = Array.from({ length: 8 }, (_, index) => gifFrame(pixelFn(index), 10));
  return Buffer.concat([header, logicalScreen, colorTable, loop, ...frames, Buffer.from([0x3b])]);
}

const helpPalette = [
  [0, 0, 0],
  [255, 180, 50],   // 1 warm amber body
  [25, 20, 15],     // 2 dark eyes/outline
  [255, 252, 240],  // 3 white face screen
  [200, 120, 20],   // 4 darker amber shade
  [255, 90, 40],    // 5 orange antenna/alert
  [120, 80, 40],    // 6 brown/gray
  [255, 220, 110],  // 7 light amber
];

function helpFramePixels(frame) {
  const width = 96;
  const pixels = new Uint8Array(width * width);
  const bounce = [3, 1, 0, 1, 3, 4, 3, 2][frame];
  const set = (x, y, color) => {
    if (x >= 0 && y >= 0 && x < width && y < width) pixels[y * width + x] = color;
  };
  const rect = (x, y, w, h, color) => {
    for (let py = y; py < y + h; py += 1) for (let px = x; px < x + w; px += 1) set(px, py, color);
  };
  const circle = (cx, cy, radius, color) => {
    for (let y = cy - radius; y <= cy + radius; y += 1) {
      for (let x = cx - radius; x <= cx + radius; x += 1) {
        if ((x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2) set(x, y, color);
      }
    }
  };
  const y = 22 + bounce;

  // Question mark / badge floating above head
  const qy = 4 + (frame % 4);
  rect(45, qy, 6, 2, 5);
  rect(49, qy + 2, 3, 3, 5);
  rect(46, qy + 5, 4, 2, 5);
  rect(46, qy + 8, 3, 2, 5);
  rect(46, qy + 12, 3, 3, 5);

  // Antenna
  rect(46, y - 10, 4, 10, 4);
  circle(48, y - 12, 3, 5);

  // Body
  circle(48, y + 28, 28, 4);
  rect(20, y + 18, 56, 30, 1);
  circle(25, y + 22, 8, 1);
  circle(71, y + 22, 8, 1);
  rect(25, y + 16, 46, 36, 1);
  rect(29, y + 23, 38, 20, 2);
  rect(32, y + 26, 32, 14, 3);

  // Curious eyes (head tilted/curious look)
  rect(37, y + 28, 5, 7, 2);
  rect(54, y + 28, 5, 7, 2);

  // Mouth - curious round "o"
  rect(45, y + 38, 6, 3, 2);

  // Hands & Feet
  rect(17, y + 31, 6, 15, 7);
  rect(73, y + 31, 6, 15, 7);
  rect(31, y + 50, 11, 8, 1);
  rect(54, y + 50, 11, 8, 1);
  return pixels;
}

function makeChime(freq1 = 659.25, freq2 = 987.77) {
  const sampleRate = 44100;
  const duration = 0.62;
  const samples = Math.floor(sampleRate * duration);
  const data = Buffer.alloc(samples * 2);
  for (let i = 0; i < samples; i += 1) {
    const time = i / sampleRate;
    const envelope = Math.exp(-5.4 * time) * Math.min(1, time * 90);
    const first = Math.sin(2 * Math.PI * freq1 * time);
    const secondTime = Math.max(0, time - 0.13);
    const second = time >= 0.13 ? Math.sin(2 * Math.PI * freq2 * secondTime) * Math.exp(-4 * secondTime) : 0;
    data.writeInt16LE(Math.round((first * 0.52 + second * 0.48) * envelope * 17000), i * 2);
  }
  const header = Buffer.alloc(44);
  header.write("RIFF", 0);
  header.writeUInt32LE(36 + data.length, 4);
  header.write("WAVEfmt ", 8);
  header.writeUInt32LE(16, 16);
  header.writeUInt16LE(1, 20);
  header.writeUInt16LE(1, 22);
  header.writeUInt32LE(sampleRate, 24);
  header.writeUInt32LE(sampleRate * 2, 28);
  header.writeUInt16LE(2, 32);
  header.writeUInt16LE(16, 34);
  header.write("data", 36);
  header.writeUInt32LE(data.length, 40);
  return Buffer.concat([header, data]);
}

writeFileSync(resolve(root, "public/taskforce-mascot.gif"), makeGif(palette, framePixels));
writeFileSync(resolve(root, "public/taskforce-chime.wav"), makeChime(659.25, 987.77));
writeFileSync(resolve(root, "public/taskforce-help.gif"), makeGif(helpPalette, helpFramePixels));
writeFileSync(resolve(root, "public/taskforce-help.wav"), makeChime(523.25, 783.99));
writeFileSync(resolve(root, "src-tauri/icons/icon.png"), makePng(128));
