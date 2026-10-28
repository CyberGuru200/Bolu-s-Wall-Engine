import Icon from "./Icon";
import WallpaperImage from "./WallpaperImage";
import WallpaperActions from "./WallpaperActions";

export default function WallpaperCard({ wallpaper, onOpen, ...actions }) {
  return (
    <article className="wallpaper-card">
      <button
        className="card-image-button"
        onClick={() => onOpen(wallpaper)}
        aria-label={`View ${wallpaper.title}`}
      >
        <WallpaperImage wallpaper={wallpaper} />
      </button>
      <span className="card-category">{wallpaper.category}</span>
      <div className="card-overlay">
        <button className="card-title" onClick={() => onOpen(wallpaper)}>
          {wallpaper.title}
        </button>
        {(wallpaper.source?.author || wallpaper.source?.license) && (
          <p className="card-meta">
            {wallpaper.source.author && <span>{wallpaper.source.author}</span>}
            {wallpaper.source.author && wallpaper.source.license && (
              <span aria-hidden="true">·</span>
            )}
            {wallpaper.source.license && (
              <span>{wallpaper.source.license}</span>
            )}
          </p>
        )}
        <div className="card-controls">
          <WallpaperActions wallpaper={wallpaper} {...actions} />
          <button
            className="card-view-button"
            onClick={() => onOpen(wallpaper)}
            aria-label={`View details for ${wallpaper.title}`}
          >
            View <Icon name="arrow" size={16} />
          </button>
        </div>
      </div>
    </article>
  );
}
