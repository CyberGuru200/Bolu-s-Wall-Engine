import originalWallpapers from "./wallpapers.js";
import newWallpapers from "./newWallpapers.js";

// The original 24-record module stays untouched. New records are kept in their
// own file with provenance, then combined here for the application.
export const original = originalWallpapers;
export const additions = newWallpapers;

const catalog = [...originalWallpapers, ...newWallpapers];

export default catalog;
