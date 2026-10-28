#!/usr/bin/env node
/**
 * Build the Phase 6B catalogue import manifest from the frontend source modules.
 *
 * The frontend catalogue is the single source of truth. Nothing here retypes a
 * title, URL, tag, or licence: the modules are imported directly and their
 * exported records are read.
 *
 * Output is deterministic: records are ordered by source id, keys are written in
 * a fixed order, and no timestamps or random values are emitted. Running this
 * twice on the same inputs must produce byte-identical JSON.
 *
 * Usage:
 *   node tools/catalogue/build_manifest.mjs [--output PATH] [--check]
 *
 *   --check   write nothing; exit non-zero if the file on disk would change.
 */

import { createHash } from "node:crypto";
import { existsSync, readFileSync, statSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(HERE, "..", "..");
const DATA_DIR = path.join(REPO_ROOT, "Front End Project", "src", "data");
const PUBLIC_DIR = path.join(REPO_ROOT, "Front End Project", "public");
const DEFAULT_OUTPUT = path.join(REPO_ROOT, "backend", "catalogue", "manifest.json");

const DATA_MODULES = ["catalog.js", "wallpapers.js", "newWallpapers.js"];

const IMAGE_FORMAT_BY_EXTENSION = {
  ".jpg": "JPEG",
  ".jpeg": "JPEG",
  ".png": "PNG",
  ".webp": "WEBP",
  ".gif": "GIF",
};

/**
 * Mirror of Django's ``django.utils.text.slugify`` (allow_unicode=False) so the
 * manifest slug is exactly what ``normalize_slug`` would produce. The Python
 * side asserts this equality rather than trusting it.
 */
export function djangoSlugify(value) {
  return String(value ?? "")
    .normalize("NFKD")
    .replace(/[^\x00-\x7F]/g, "")
    .replace(/[^\w\s-]/g, "")
    .trim()
    .toLowerCase()
    .replace(/[-\s]+/g, "-");
}

function sha256File(absPath) {
  return createHash("sha256").update(readFileSync(absPath)).digest("hex");
}

function repoRelative(absPath) {
  return path.relative(REPO_ROOT, absPath).split(path.sep).join("/");
}

function classify(record) {
  if (typeof record.url !== "string" || !record.url) return "no-url";
  if (record.url.startsWith("/")) return "local";
  if (/^https?:\/\//i.test(record.url)) return "external";
  return "unsupported-url";
}

function parseArgs(argv) {
  const args = { output: DEFAULT_OUTPUT, check: false };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--check") args.check = true;
    else if (arg === "--output") {
      args.output = path.resolve(argv[index + 1] ?? "");
      index += 1;
    } else if (arg === "--help" || arg === "-h") {
      args.help = true;
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }
  return args;
}

async function loadCatalogue() {
  const catalogPath = path.join(DATA_DIR, "catalog.js");
  const aggregate = await import(`file://${catalogPath}`);
  const records = aggregate.default;

  const originals = await import(`file://${path.join(DATA_DIR, "wallpapers.js")}`);
  const additions = await import(`file://${path.join(DATA_DIR, "newWallpapers.js")}`);

  return {
    records,
    originals: originals.default,
    additions: additions.default,
  };
}

const TAG_ORDER_NOTE =
  "Tag order is the order declared on each record; global tags are sorted by slug.";

function buildManifest({ records }) {
  const localRecords = records.filter((record) => classify(record) === "local");
  const externalRecords = records.filter((record) => classify(record) !== "local");

  const slugOwners = new Map();
  const tagUsage = new Map();
  const categoryUsage = new Map();
  const problems = [];

  const selected = localRecords
    .slice()
    .sort((a, b) => a.id - b.id)
    .map((record) => {
      const slug = djangoSlugify(record.title);
      if (!slug) {
        problems.push({ source_id: record.id, problem: "empty slug" });
      }
      if (slugOwners.has(slug)) {
        problems.push({
          source_id: record.id,
          problem: `duplicate slug "${slug}" (also used by ${slugOwners.get(slug)})`,
        });
      }
      slugOwners.set(slug, record.id);

      const source = record.source ?? {};
      const publicPath = record.url.replace(/^\/+/, "");
      const absolutePath = path.join(PUBLIC_DIR, publicPath);
      const extension = path.extname(absolutePath).toLowerCase();
      const format = IMAGE_FORMAT_BY_EXTENSION[extension] ?? null;

      if (!existsSync(absolutePath)) {
        problems.push({ source_id: record.id, problem: `missing file ${publicPath}` });
      }

      const fileSize = existsSync(absolutePath) ? statSync(absolutePath).size : null;
      const fileSha256 = existsSync(absolutePath) ? sha256File(absolutePath) : null;

      if (fileSha256 && source.fileSha256 && fileSha256 !== source.fileSha256) {
        problems.push({
          source_id: record.id,
          problem: "delivered file sha256 does not match source.fileSha256",
        });
      }

      if (!Number.isInteger(record.width) || !Number.isInteger(record.height)) {
        problems.push({ source_id: record.id, problem: "missing integer width/height" });
      }

      if (!source.license || !source.licenseUrl) {
        problems.push({ source_id: record.id, problem: "missing licence name or URL" });
      }

      const categorySlug = djangoSlugify(record.category);
      categoryUsage.set(record.category, (categoryUsage.get(record.category) ?? 0) + 1);

      const tags = (record.tags ?? [])
        .map((name) => ({ name, slug: djangoSlugify(name) }))
        .sort((a, b) => a.slug.localeCompare(b.slug));
      for (const tag of tags) {
        tagUsage.set(tag.slug, (tagUsage.get(tag.slug) ?? 0) + 1);
      }

      return {
        source_id: record.id,
        title: record.title,
        slug,
        description: record.description ?? "",
        category: { name: record.category, slug: categorySlug },
        tags,
        image: {
          source_path: repoRelative(absolutePath),
          public_url: `/${publicPath}`,
          sha256: fileSha256,
          file_size: fileSize,
          width: record.width ?? null,
          height: record.height ?? null,
          format,
        },
        source_url: source.sourceUrl ?? "",
        license: {
          name: source.license ?? "",
          url: source.licenseUrl ?? "",
          status: source.license ? "documented" : "unknown",
          id: source.licenseId ?? "",
          text_path: source.licenseFile
            ? repoRelative(path.join(PUBLIC_DIR, source.licenseFile.replace(/^\/+/, "")))
            : "",
        },
        attribution: {
          author: source.author ?? "",
          collection: source.collection ?? "",
          upstream: {
            commit: source.commit ?? "",
            original_path: source.originalPath ?? "",
            original_sha256: source.originalSha256 ?? "",
            original_width: source.originalWidth ?? null,
            original_height: source.originalHeight ?? null,
            original_format: source.originalFormat ?? "",
            delivered_sha256: source.fileSha256 ?? "",
            blob_sha: source.blobSha ?? "",
            modification: source.modified ?? "",
            retrieved: source.retrieved ?? "",
          },
        },
        status: "published",
      };
    });

  const excluded = externalRecords
    .slice()
    .sort((a, b) => a.id - b.id)
    .map((record) => ({
      source_id: record.id,
      title: record.title,
      reason: "external-url-unverified",
      detail:
        "External image URL with no per-record author or licence metadata; not imported in this phase.",
    }));

  const categories = [...categoryUsage.entries()]
    .map(([name, count]) => ({ name, slug: djangoSlugify(name), records: count }))
    .sort((a, b) => a.slug.localeCompare(b.slug));

  const tags = [...tagUsage.entries()]
    .map(([slug, count]) => {
      const record = selected.find((item) => item.tags.some((tag) => tag.slug === slug));
      return { name: record.tags.find((tag) => tag.slug === slug).name, slug, records: count };
    })
    .sort((a, b) => a.slug.localeCompare(b.slug));

  const declaredCategories = new Set(categories.map((category) => category.slug));
  const declaredTags = new Set(tags.map((tag) => tag.slug));
  for (const record of selected) {
    if (!declaredCategories.has(record.category.slug)) {
      problems.push({ source_id: record.source_id, problem: "category not declared" });
    }
    for (const tag of record.tags) {
      if (!declaredTags.has(tag.slug)) {
        problems.push({ source_id: record.source_id, problem: `tag not declared: ${tag.slug}` });
      }
    }
  }

  const licenseCoverage = selected.reduce((acc, record) => {
    acc[record.license.name] = (acc[record.license.name] ?? 0) + 1;
    return acc;
  }, {});

  return {
    manifest_version: 1,
    phase: "6B",
    kind: "catalogue-import-manifest",
    notes: [
      "Generated from the frontend modules; do not edit by hand.",
      "Only verified local-image records are selected. External Pexels records are excluded and never imported.",
      "The Wallpaper model has no author or collection field; attribution is preserved here for a future schema decision.",
      TAG_ORDER_NOTE,
    ],
    source: {
      aggregate_module: repoRelative(path.join(DATA_DIR, "catalog.js")),
      modules: DATA_MODULES.map((name) => {
        const absPath = path.join(DATA_DIR, name);
        return { path: repoRelative(absPath), sha256: sha256File(absPath) };
      }),
      total_records: records.length,
      original_records: records.filter((record) => record.id <= 24).length,
      added_records: records.filter((record) => record.id > 24).length,
    },
    selection: {
      policy: "verified-local-image-records-only",
      selected: selected.length,
      excluded: excluded.length,
      excluded_records: excluded,
    },
    summary: {
      categories: categories.length,
      tags: tags.length,
      license_coverage: licenseCoverage,
    },
    categories,
    tags,
    records: selected,
    problems,
  };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    console.log("Usage: node tools/catalogue/build_manifest.mjs [--output PATH] [--check]");
    return;
  }

  const catalogue = await loadCatalogue();
  const manifest = buildManifest(catalogue);

  if (manifest.problems.length) {
    console.error("Manifest contains problems and was not written:");
    for (const problem of manifest.problems) {
      console.error(`  source_id=${problem.source_id}: ${problem.problem}`);
    }
    process.exitCode = 1;
    return;
  }

  const serialized = `${JSON.stringify(manifest, null, 2)}\n`;

  if (args.check) {
    const current = existsSync(args.output) ? readFileSync(args.output, "utf8") : null;
    if (current === serialized) {
      console.log(`Manifest is up to date: ${repoRelative(args.output)}`);
      return;
    }
    console.error(`Manifest is missing or stale: ${repoRelative(args.output)}`);
    process.exitCode = 1;
    return;
  }

  writeFileSync(args.output, serialized);
  console.log(
    JSON.stringify(
      {
        output: repoRelative(args.output),
        total_source_records: manifest.source.total_records,
        selected: manifest.selection.selected,
        excluded: manifest.selection.excluded,
        categories: manifest.categories.length,
        tags: manifest.tags.length,
        sha256: createHash("sha256").update(serialized).digest("hex"),
      },
      null,
      2,
    ),
  );
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
