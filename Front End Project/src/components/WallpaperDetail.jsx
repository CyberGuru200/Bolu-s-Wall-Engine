import { useEffect, useRef } from "react";
import Modal from "./Modal";
import WallpaperImage from "./WallpaperImage";
import WallpaperActions from "./WallpaperActions";
import Icon from "./Icon";

export default function WallpaperDetail({
  wallpaper,
  catalog,
  onClose,
  onOpen,
  downloadNotice,
  detailLoading = false,
  libraryNote = "Likes and saves stay in this browser.",
  ...actions
}) {
  const heading = useRef(null);
  const related = catalog
    .filter(
      (item) =>
        item.category === wallpaper.category && item.id !== wallpaper.id,
    )
    .slice(0, 3);
  const source = wallpaper.source || {};
  const hasProvenance = Boolean(
    source.author ||
      source.collection ||
      source.license ||
      source.licenseUrl ||
      source.sourceUrl ||
      source.licenseFile,
  );
  useEffect(() => {
    heading.current.focus();
  }, [wallpaper.id]);
  return (
    <Modal titleId="detail-title" onClose={onClose} className="detail-modal">
      <div className="detail-image">
        <WallpaperImage key={wallpaper.id} wallpaper={wallpaper} eager />
      </div>
      <div className="detail-content">
        <span className="eyebrow">{wallpaper.category} / Wallpaper</span>
        <h2 id="detail-title" ref={heading} tabIndex={-1}>
          {wallpaper.title}
        </h2>
        {wallpaper.description && <p>{wallpaper.description}</p>}
        {wallpaper.tags?.length > 0 && (
          <ul className="tag-list">
            {wallpaper.tags.map((tag) => (
              <li key={tag}>{tag}</li>
            ))}
          </ul>
        )}
        <WallpaperActions wallpaper={wallpaper} {...actions} expanded />
        {hasProvenance && (
          <section className="provenance" aria-label="Source and license">
            <p className="eyebrow">SOURCE &amp; LICENSE</p>
            <dl>
              {wallpaper.source.author && (
                <div>
                  <dt>Artist</dt>
                  <dd>{wallpaper.source.author}</dd>
                </div>
              )}
              {wallpaper.source.collection && (
                <div>
                  <dt>Collection</dt>
                  <dd>{wallpaper.source.collection}</dd>
                </div>
              )}
              {(wallpaper.source.license || wallpaper.source.licenseUrl) && (
                <div>
                  <dt>License</dt>
                  <dd>
                    {wallpaper.source.licenseUrl ? (
                      <a
                        href={wallpaper.source.licenseUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        {wallpaper.source.license || "License"}
                      </a>
                    ) : (
                      wallpaper.source.license
                    )}
                  </dd>
                </div>
              )}
              {wallpaper.source.modified && (
                <div>
                  <dt>Delivery copy</dt>
                  <dd>{wallpaper.source.modified}</dd>
                </div>
              )}
            </dl>
            <div className="provenance-links">
              {wallpaper.source.sourceUrl && (
                <a
                  className="text-link"
                  href={wallpaper.source.sourceUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Original artwork <Icon name="external" size={14} />
                </a>
              )}
              {wallpaper.source.licenseFile && (
                <a
                  className="text-link"
                  href={wallpaper.source.licenseFile}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  License text <Icon name="external" size={14} />
                </a>
              )}
            </div>
          </section>
        )}
        <p className="detail-note">
          Download uses the image supplied by the collection.{" "}
          {detailLoading ? "Loading full details…" : libraryNote}
        </p>
        {downloadNotice}
        <a
          className="text-link"
          href={wallpaper.url}
          target="_blank"
          rel="noopener noreferrer"
        >
          {wallpaper.source ? "Open full-size image" : "Open source image"}{" "}
          <Icon name="external" size={15} />
        </a>
        {related.length > 0 && (
          <section className="related-section" aria-labelledby="related-title">
            <h3 id="related-title">More in {wallpaper.category}</h3>
            <div className="related-grid">
              {related.map((item) => (
                <button
                  key={item.id}
                  className="related-card"
                  onClick={() => onOpen(item)}
                  aria-label={`View ${item.title}`}
                >
                  <WallpaperImage wallpaper={item} />
                  <span>{item.title}</span>
                </button>
              ))}
            </div>
          </section>
        )}
      </div>
    </Modal>
  );
}
