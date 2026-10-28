import Icon from "./Icon";

export default function WallpaperActions({
  wallpaper,
  liked,
  saved,
  onLike,
  onSave,
  onDownload,
  downloadingId,
  expanded = false,
}) {
  return (
    <div className={`wallpaper-actions ${expanded ? "expanded-actions" : ""}`}>
      <button
        className={`icon-button ${liked ? "is-liked" : ""}`}
        aria-label={`${liked ? "Unlike" : "Like"} ${wallpaper.title}`}
        aria-pressed={liked}
        onClick={() => onLike(wallpaper.id)}
        title={liked ? "Unlike" : "Like"}
      >
        <Icon name="heart" />
        {expanded && <span>{liked ? "Liked" : "Like"}</span>}
      </button>
      <button
        className={`icon-button ${saved ? "is-saved" : ""}`}
        aria-label={`${saved ? "Unsave" : "Save"} ${wallpaper.title}`}
        aria-pressed={saved}
        onClick={() => onSave(wallpaper.id)}
        title={saved ? "Remove from saved" : "Save"}
      >
        <Icon name="bookmark" />
        {expanded && <span>{saved ? "Saved" : "Save"}</span>}
      </button>
      <button
        className={expanded ? "button primary" : "icon-button"}
        aria-label={`Download ${wallpaper.title}`}
        onClick={() => onDownload(wallpaper)}
        disabled={downloadingId !== null}
        title="Download image"
      >
        <Icon name="download" />
        {expanded && (
          <span>
            {downloadingId === wallpaper.id ? "Downloading…" : "Download"}
          </span>
        )}
      </button>
    </div>
  );
}
