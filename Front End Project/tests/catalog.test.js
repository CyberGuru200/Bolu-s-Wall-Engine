import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import wallpapers from "../src/data/wallpapers.js";
import {
  getCategories,
  filterWallpapers,
  toggleId,
  validIds,
} from "../src/lib/catalog.js";

// Hash is taken directly from the archived source, not a rewritten fixture.
test("original catalog: all 24 records remain unchanged", () => {
  assert.equal(wallpapers.length, 24);
  assert.equal(new Set(wallpapers.map((item) => item.id)).size, 24);
  const hash = createHash("sha256")
    .update(readFileSync(new URL("../src/data/wallpapers.js", import.meta.url)))
    .digest("hex");
  assert.equal(
    hash,
    "6b36c389c6dc16b1ac78ac02bfa7e49c86b4993c09ab1137b96f1423818ab013",
  );
});
test("category counts are data-driven", () => {
  assert.deepEqual(
    getCategories(wallpapers),
    ["Anime", "Abstract", "Minimalist", "Colored"].map((name) => ({
      name,
      count: 6,
    })),
  );
  assert.equal(
    getCategories([...wallpapers, { id: 25, category: "Nature" }]).at(-1).name,
    "Nature",
  );
});
test("category, search, and collections combine", () => {
  assert.equal(filterWallpapers(wallpapers, { category: "Anime" }).length, 6);
  assert.deepEqual(
    filterWallpapers(wallpapers, {
      category: "Anime",
      query: "  TOKYO neon ",
      view: "liked",
      liked: [1, 6, 19],
    }).map((item) => item.id),
    [6],
  );
  assert.equal(
    filterWallpapers(wallpapers, { category: "Abstract", query: "tokyo" })
      .length,
    0,
  );
  assert.equal(filterWallpapers(wallpapers, { query: "minimalist" }).length, 6);
  assert.deepEqual(
    filterWallpapers(wallpapers, { view: "saved", saved: [9] }).map(
      (item) => item.id,
    ),
    [9],
  );
});
test("supports optional tags without changing catalog", () => {
  assert.equal(
    filterWallpapers([{ title: "Sky", category: "Nature", tags: ["blue"] }], {
      query: "blue",
    }).length,
    1,
  );
});
test("toggle and validate collection IDs without mutation", () => {
  const ids = [1, 3];
  assert.deepEqual(toggleId(ids, 3), [1]);
  assert.deepEqual(toggleId(ids, 4), [1, 3, 4]);
  assert.deepEqual(ids, [1, 3]);
  assert.equal(validIds([1, 24], wallpapers), true);
  assert.equal(validIds([25], wallpapers), false);
  assert.equal(validIds("1", wallpapers), false);
});
test("sorting leaves original order intact", () => {
  const before = wallpapers.map((item) => item.id);
  const sorted = filterWallpapers(wallpapers, { sort: "title" });
  assert.equal(sorted[0].title, "Abstract Lines");
  assert.deepEqual(
    wallpapers.map((item) => item.id),
    before,
  );
});
