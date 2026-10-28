/**
 * Adapters between the Django API schema and the approved UI model.
 *
 * The API identifies wallpapers by slug and nests category/tags, while the
 * existing components expect a flat category name and a stable `id`. Nothing
 * here invents metadata: absent backend fields stay absent.
 */

export function wallpaperId(wallpaper) {
  return wallpaper?.slug ?? wallpaper?.id;
}

export function toUiWallpaper(wallpaper) {
  if (!wallpaper) return null;
  return {
    id: wallpaperId(wallpaper),
    slug: wallpaper.slug,
    title: wallpaper.title,
    description: wallpaper.description || "",
    url: wallpaper.thumbnail_url || wallpaper.url,
    fullUrl: wallpaper.url,
    thumbnailUrl: wallpaper.thumbnail_url || wallpaper.url,
    category: wallpaper.category?.name || "Uncategorised",
    categorySlug: wallpaper.category?.slug || "",
    tags: Array.isArray(wallpaper.tags)
      ? wallpaper.tags.map((tag) => tag.name).filter(Boolean)
      : [],
    tagSlugs: Array.isArray(wallpaper.tags)
      ? wallpaper.tags.map((tag) => tag.slug).filter(Boolean)
      : [],
    width: wallpaper.width ?? null,
    height: wallpaper.height ?? null,
    orientation: wallpaper.orientation ?? null,
    imageSource: wallpaper.image_source ?? null,
    downloadCount: wallpaper.download_count ?? 0,
    publishedAt: wallpaper.published_at ?? null,
  };
}

/**
 * Detail responses add provenance. The backend stores an optional source URL,
 * a licence, and (since Phase 6C) optional author/collection credit strings.
 * This approved UI renders the licence and source URL only; the credit strings
 * are deliberately left unmapped rather than fabricated into the layout.
 */
export function toUiWallpaperDetail(wallpaper) {
  const base = toUiWallpaper(wallpaper);
  if (!base) return null;
  const license = wallpaper.license || {};
  const source = {
    ...(license.name ? { license: license.name } : {}),
    ...(license.url ? { licenseUrl: license.url } : {}),
    ...(license.status ? { licenseStatus: license.status } : {}),
    ...(wallpaper.source_url ? { sourceUrl: wallpaper.source_url } : {}),
  };
  return {
    ...base,
    url: wallpaper.url || base.url,
    source: Object.keys(source).length ? source : undefined,
  };
}

export function toUiCategory(category) {
  return {
    id: category.slug,
    name: category.name,
    slug: category.slug,
    description: category.description || "",
    imageUrl: category.image_url || "",
    count: category.wallpaper_count ?? 0,
  };
}

export function toUiTag(tag) {
  return {
    id: tag.slug,
    name: tag.name,
    slug: tag.slug,
    count: tag.wallpaper_count ?? 0,
  };
}

export function librarySlugs(envelope) {
  const results = Array.isArray(envelope?.results) ? envelope.results : [];
  return results
    .map((item) => item?.wallpaper?.slug)
    .filter((slug) => typeof slug === "string" && slug.length > 0);
}

/**
 * Map UI state to the query parameters the API actually documents.
 * Unsupported local-only state (the "collection" sort) is omitted.
 */
export function toWallpaperQuery({
  search = "",
  categorySlug = "",
  tagSlugs = [],
  orientation = "",
  sort = "collection",
} = {}) {
  const query = {};
  const term = search.trim();
  if (term) query.search = term.slice(0, 100);
  if (categorySlug) query.category = categorySlug;
  const tags = (Array.isArray(tagSlugs) ? tagSlugs : []).filter(Boolean);
  if (tags.length) query.tag = tags;
  if (orientation) query.orientation = orientation;
  if (sort === "title") query.ordering = "title";
  return query;
}

function splitName(name) {
  const parts = String(name || "")
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  return {
    first: parts[0] || "",
    last: parts.slice(1).join(" "),
  };
}

/** allauth returns a display name; the UI only needs a short label. */
export function toUiUser(profile, fallback = {}) {
  const name = String(profile?.display_name || profile?.username || "")
    .trim();
  const parts = splitName(name || fallback.name || "");
  return {
    id: profile?.id ?? null,
    username: profile?.username || "",
    email: profile?.email || "",
    displayName: name || fallback.email || "Signed in",
    firstName: parts.first,
    providers: profile?.providers || [],
    likesCount: profile?.likes_count ?? 0,
    savedCount: profile?.saved_count ?? 0,
  };
}
