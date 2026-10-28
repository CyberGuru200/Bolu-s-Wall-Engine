import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync, existsSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import catalog, { original, additions } from "../src/data/catalog.js";
import originalSource from "../src/data/wallpapers.js";
import {
  getCategories,
  filterWallpapers,
  validIds,
} from "../src/lib/catalog.js";

const appRoot = new URL("../", import.meta.url);
const assetPath = (record) => new URL(`public${record.url}`, appRoot);

function pngSize(buffer) {
  assert.equal(buffer.toString("ascii", 1, 4), "PNG", "PNG signature");
  return {
    width: buffer.readUInt32BE(16),
    height: buffer.readUInt32BE(20),
  };
}

function jpegSize(buffer) {
  assert.equal(buffer[0], 0xff, "JPEG SOI");
  assert.equal(buffer[1], 0xd8, "JPEG SOI");
  let offset = 2;
  while (offset < buffer.length) {
    if (buffer[offset] !== 0xff) {
      offset += 1;
      continue;
    }
    const marker = buffer[offset + 1];
    if (
      marker === 0xd8 ||
      marker === 0x01 ||
      (marker >= 0xd0 && marker <= 0xd7)
    ) {
      offset += 2;
      continue;
    }
    const length = buffer.readUInt16BE(offset + 2);
    if (marker >= 0xc0 && marker <= 0xc3) {
      return {
        height: buffer.readUInt16BE(offset + 5),
        width: buffer.readUInt16BE(offset + 7),
      };
    }
    offset += 2 + length;
  }
  throw new Error("JPEG size marker not found");
}

test("aggregate catalog contains 56 complete, unique records", () => {
  assert.equal(catalog.length, 56);
  assert.equal(new Set(catalog.map((item) => item.id)).size, 56);
  assert.deepEqual(
    catalog.map((item) => item.id),
    Array.from({ length: 56 }, (_, index) => index + 1),
  );
  assert.equal(new Set(catalog.map((item) => item.url)).size, 56);
  for (const record of catalog) {
    assert.ok(record.title.trim(), `title for ${record.id}`);
    assert.ok(record.category.trim(), `category for ${record.id}`);
    assert.match(record.url, /^https:\/\/|\/wallpapers\//);
  }
});

test("the original 24 records are preserved byte-for-byte and by value", () => {
  assert.deepEqual(original, originalSource);
  assert.equal(original.length, 24);
  const hash = createHash("sha256")
    .update(readFileSync(new URL("../src/data/wallpapers.js", import.meta.url)))
    .digest("hex");
  assert.equal(
    hash,
    "6b36c389c6dc16b1ac78ac02bfa7e49c86b4993c09ab1137b96f1423818ab013",
  );
  assert.deepEqual(catalog.slice(0, 24), originalSource);
});

test("32 added records declare artist, license, and pinned source", () => {
  assert.equal(additions.length, 32);
  assert.equal(new Set(additions.map((item) => item.id)).size, 32);
  assert.equal(
    new Set(additions.map((item) => item.source.fileSha256)).size,
    32,
  );
  assert.equal(
    new Set(additions.map((item) => item.source.originalPath)).size,
    32,
  );
  assert.equal(
    additions.filter((item) => item.source.licenseId === "CC-BY-SA-4.0").length,
    16,
  );
  assert.equal(
    additions.filter((item) => item.source.licenseId === "LGPL-3.0-only")
      .length,
    16,
  );
  for (const record of additions) {
    assert.ok(record.source.author.trim(), `artist for ${record.id}`);
    assert.ok(record.source.collection.trim(), `collection for ${record.id}`);
    assert.match(
      record.source.sourceUrl,
      /^https:\/\/github\.com\/KDE\/plasma-workspace-wallpapers\/blob\/3e4537eb3852a1c769f6fa003e74d06260c266fb\//,
    );
    assert.ok(
      record.source.license === "CC BY-SA 4.0" ||
        record.source.license === "LGPLv3",
    );
    assert.match(record.url, /^\/wallpapers\/kde\/[a-z0-9-]+\.(jpg|png)$/);
    assert.ok(record.width > 0 && record.height > 0);
  }
  const originalUrls = new Set(original.map((item) => item.url));
  for (const record of additions) {
    assert.equal(originalUrls.has(record.url), false);
  }
});

test("delivered image files exist, decode by header, and match recorded hashes", () => {
  for (const record of additions) {
    const file = assetPath(record);
    assert.ok(existsSync(file), `missing ${record.url}`);
    assert.ok(statSync(file).size > 10_000, `suspiciously small ${record.url}`);
    const buffer = readFileSync(file);
    const size =
      buffer.toString("ascii", 1, 4) === "PNG"
        ? pngSize(buffer)
        : jpegSize(buffer);
    assert.equal(size.width, record.width, `width of ${record.url}`);
    assert.equal(size.height, record.height, `height of ${record.url}`);
    assert.equal(
      createHash("sha256").update(buffer).digest("hex"),
      record.source.fileSha256,
      `hash of ${record.url}`,
    );
  }
});

test("license texts are present and match declared licenses", () => {
  const cc = readFileSync(
    new URL("../public/licenses/CC-BY-SA-4.0.txt", import.meta.url),
    "utf8",
  );
  const lgpl = readFileSync(
    new URL("../public/licenses/LGPL-3.0.txt", import.meta.url),
    "utf8",
  );
  assert.match(cc, /Attribution-ShareAlike 4\.0 International/);
  assert.match(lgpl, /GNU LESSER GENERAL PUBLIC LICENSE/);
  assert.match(lgpl, /Version 3, 29 June 2007/);
});

test("categories and search cover the expanded catalog", () => {
  assert.deepEqual(getCategories(catalog), [
    { name: "Anime", count: 6 },
    { name: "Abstract", count: 21 },
    { name: "Minimalist", count: 9 },
    { name: "Colored", count: 6 },
    { name: "Nature", count: 9 },
    { name: "Space", count: 2 },
    { name: "Illustration", count: 3 },
  ]);
  assert.equal(filterWallpapers(catalog, { category: "Nature" }).length, 9);
  assert.equal(filterWallpapers(catalog, { query: "coast" }).length, 1);
  assert.equal(filterWallpapers(catalog, { query: "illustration" }).length, 3);
  assert.equal(filterWallpapers(catalog, { category: "Space" }).length, 2);
  assert.deepEqual(
    filterWallpapers(catalog, {
      query: "meteors",
      sort: "title",
    }).map((item) => item.id),
    [47],
  );
  assert.equal(validIds([1, 25, 56], catalog), true);
  assert.equal(validIds([57], catalog), false);
});

test("assets live inside the project and resolve to the shipped directory", () => {
  assert.match(
    fileURLToPath(assetPath(additions[0])),
    /\/public\/wallpapers\/kde\//,
  );
});
