import { useCallback, useEffect, useState } from "react";
import localWallpapers from "../data/catalog";
import localCollections, { newToLibrary } from "../data/collections";
import { getCategories } from "../lib/catalog";
import { toUiCategory, toUiTag, toUiWallpaper } from "../lib/adapters";

const byId = (id) => localWallpapers.find((wallpaper) => wallpaper.id === id);
const localFeatured = [6, 9, 19].map(byId).filter(Boolean);
const localRecent = newToLibrary.ids.slice(0, 4).map(byId).filter(Boolean);

export const LOCAL_CATALOGUE = Object.freeze({
  mode: "local",
  wallpapers: localWallpapers,
  categories: getCategories(localWallpapers),
  tags: [],
  featured: localFeatured,
  recentAdditions: localRecent,
  collections: localCollections,
  newToLibrary,
  total: localWallpapers.length,
  truncated: false,
  loading: false,
  error: null,
});

const EMPTY_API_CATALOGUE = {
  ...LOCAL_CATALOGUE,
  mode: "api",
  wallpapers: [],
  categories: [],
  featured: [],
  recentAdditions: [],
  collections: [],
  newToLibrary: null,
  total: 0,
  loading: true,
};

function newestFirst(a, b) {
  return String(b.publishedAt || "").localeCompare(String(a.publishedAt || ""));
}

/**
 * Load the catalogue once and adapt it to the UI model.
 *
 * The bundled catalogue remains the source only when no API base URL is
 * configured; an API failure is reported, never masked with local data.
 */
export default function useCatalogue(api) {
  const [state, setState] = useState(api ? EMPTY_API_CATALOGUE : LOCAL_CATALOGUE);

  const load = useCallback(async () => {
    if (!api) return;
    setState((current) => ({ ...current, loading: true, error: null }));
    try {
      const [categories, tags, wallpapers, popular] = await Promise.all([
        api.listCategories(),
        api.listTags(),
        api.listWallpapers(),
        api.listPopular(),
      ]);
      const uiWallpapers = wallpapers.results.map(toUiWallpaper);
      setState({
        mode: "api",
        wallpapers: uiWallpapers,
        categories: categories.results.map(toUiCategory),
        tags: tags.results.map(toUiTag),
        featured: popular.results.slice(0, 3).map(toUiWallpaper),
        recentAdditions: [...uiWallpapers].sort(newestFirst).slice(0, 4),
        collections: [],
        newToLibrary: null,
        total: wallpapers.count,
        truncated: wallpapers.truncated || categories.truncated,
        loading: false,
        error: null,
      });
    } catch (error) {
      setState((current) => ({
        ...current,
        loading: false,
        error:
          error?.message ||
          "The wallpaper API could not be reached. Check the API base URL.",
      }));
    }
  }, [api]);

  useEffect(() => {
    load();
  }, [load]);

  return { ...state, reload: load };
}
