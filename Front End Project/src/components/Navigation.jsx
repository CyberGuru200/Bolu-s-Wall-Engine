import Icon from "./Icon";

const mainLinks = [
  ["home", "Home", "home"],
  ["explore", "Explore", "explore"],
  ["categories", "Categories", "grid"],
];
const libraryLinks = [
  ["liked", "Liked wallpapers", "heart"],
  ["saved", "Saved wallpapers", "bookmark"],
];

export default function Navigation({
  view,
  onNavigate,
  likedCount,
  savedCount,
  mobileOpen,
  onClose,
  storageLabel = "Stored on this device",
}) {
  const link = ([id, label, icon]) => (
    <a
      key={id}
      href={`#${id}`}
      onClick={(event) => {
        event.preventDefault();
        onNavigate(id);
      }}
      className={`nav-link ${view === id ? "active" : ""}`}
      aria-label={label}
      aria-current={view === id ? "page" : undefined}
    >
      <Icon name={icon} />
      <span>{label.replace(" wallpapers", "")}</span>
      {["liked", "saved"].includes(id) && (
        <span className="nav-count">
          {id === "liked" ? likedCount : savedCount}
        </span>
      )}
    </a>
  );
  return (
    <>
      {mobileOpen && (
        <button
          className="nav-backdrop"
          aria-label="Close navigation"
          onClick={onClose}
        />
      )}
      <aside
        className={`sidebar ${mobileOpen ? "is-open" : ""}`}
        id="site-navigation"
      >
        <a
          className="brand"
          href="#home"
          onClick={(event) => {
            event.preventDefault();
            onNavigate("home");
          }}
          aria-label="Bolu's Wall Engine home"
        >
          <span className="brand-mark">
            <Icon name="image" size={25} />
          </span>
          <span>
            Bolu’s<span className="brand-subtitle">WALL ENGINE</span>
          </span>
        </a>
        <nav aria-label="Main navigation">
          <div className="nav-group">{mainLinks.map(link)}</div>
          <p className="nav-label">YOUR COLLECTION</p>
          <div className="nav-group">{libraryLinks.map(link)}</div>
        </nav>
        <div className="sidebar-note">
          <span className="small-mark">
            <Icon name="bookmark" size={18} />
          </span>
          <strong>Your personal collection.</strong>
          <p>Like or save a wallpaper to find it here later.</p>
          <span className="local-label">
            <span /> {storageLabel}
          </span>
        </div>
        <div className="sidebar-footer">
          <span>Bolu’s Wall Engine</span>
          <span>Wallpaper library</span>
        </div>
      </aside>
    </>
  );
}
