// Catalog operations are independent of React and ready for a future data adapter.
export function getCategories(catalog) {
  return [...new Set(catalog.map((wallpaper) => wallpaper.category))].map(
    (name) => ({
      name,
      count: catalog.filter((wallpaper) => wallpaper.category === name).length,
    }),
  );
}

export function filterWallpapers(
  catalog,
  {
    category = "All",
    query = "",
    view = "home",
    liked = [],
    saved = [],
    sort = "collection",
  } = {},
) {
  const terms = query.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
  const results = catalog.filter((wallpaper) => {
    const searchable = [
      wallpaper.title,
      wallpaper.category,
      ...(wallpaper.tags || []),
    ]
      .join(" ")
      .toLocaleLowerCase();
    return (
      (category === "All" || wallpaper.category === category) &&
      (view !== "liked" || liked.includes(wallpaper.id)) &&
      (view !== "saved" || saved.includes(wallpaper.id)) &&
      terms.every((term) => searchable.includes(term))
    );
  });
  return sort === "title"
    ? results.sort((a, b) => a.title.localeCompare(b.title))
    : results;
}

export function toggleId(ids, id) {
  return ids.includes(id) ? ids.filter((item) => item !== id) : [...ids, id];
}

export function validIds(value, catalog) {
  return (
    Array.isArray(value) &&
    value.every((id) => catalog.some((item) => item.id === id))
  );
}
