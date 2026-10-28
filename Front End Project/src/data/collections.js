// Editorial groupings built from real catalog records. These are curated
// selections, not popularity or activity data.
export const newToLibrary = {
  id: "new",
  title: "New to the library",
  description:
    "The latest additions to the collection, each with its source and license recorded.",
  representative: 51,
  ids: Array.from({ length: 32 }, (_, index) => index + 25),
};

const collections = [
  {
    id: "quiet",
    title: "Quiet minimal",
    description: "Calm geometry, soft light, and room to breathe.",
    representative: 31,
    ids: [13, 14, 15, 16, 17, 18, 31, 36, 40],
  },
  {
    id: "coastlines",
    title: "Coastlines",
    description: "Still water, open horizons, and the edge of the tide.",
    representative: 54,
    ids: [27, 30, 34, 54, 56],
  },
  {
    id: "after-dark",
    title: "After dark",
    description: "Night skies, deep shadow, and low-lit color.",
    representative: 42,
    ids: [5, 8, 15, 29, 32, 42, 47],
  },
  {
    id: "illustrated",
    title: "Illustrated worlds",
    description: "Painted places and graphic escapes.",
    representative: 51,
    ids: [1, 2, 3, 4, 51, 52, 55],
  },
];

export default collections;
