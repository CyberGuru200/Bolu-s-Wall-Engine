import { useEffect, useMemo, useRef, useState } from "react";
import bundledWallpapers from "./data/catalog";
import { filterWallpapers, toggleId, validIds } from "./lib/catalog";
import { downloadFromUrl, downloadWallpaper } from "./lib/download";
import useLocalPreference from "./hooks/useLocalPreference";
import useCatalogue from "./hooks/useCatalogue";
import useSession from "./hooks/useSession";
import { apiClient, apiMode, googleClientId, sessionStore } from "./lib/appApi";
import { toUiWallpaperDetail } from "./lib/adapters";
import Icon from "./components/Icon";
import Navigation from "./components/Navigation";
import WallpaperCard from "./components/WallpaperCard";
import WallpaperImage from "./components/WallpaperImage";
import WallpaperDetail from "./components/WallpaperDetail";
import Modal from "./components/Modal";
import GoogleSignIn from "./components/GoogleSignIn";
import "./App.css";

const views = ["home", "explore", "categories", "liked", "saved"];
const currentView = () =>
  views.includes(location.hash.slice(1)) ? location.hash.slice(1) : "home";
const titles = {
  home: "Discover wallpapers",
  explore: "Explore the collection",
  categories: "Browse by category",
  liked: "Liked wallpapers",
  saved: "Saved wallpapers",
};
const subtitles = {
  home: "A considered collection of images for the screens you look at most.",
  explore: "All wallpapers, ready to explore.",
  categories: "Explore the collection by style.",
  liked: "The wallpapers that caught your eye.",
  saved: "Your next screen refresh, kept in one place.",
};
function App() {
  const catalogue = useCatalogue(apiClient);
  const {
    wallpapers,
    categories,
    featured,
    recentAdditions,
    collections,
    newToLibrary,
  } = catalogue;
  const sessionState = useSession(sessionStore);
  const signedIn = sessionState.status === "authenticated";
  const [view, setView] = useState(currentView);
  const [activeCategory, setActiveCategory] = useState("All");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState("collection");
  const [likedLocal, setLikedLocal, likesUnavailable] = useLocalPreference(
    "bwe:liked",
    [],
    (value) => validIds(value, bundledWallpapers),
  );
  const [savedLocal, setSavedLocal, savesUnavailable] = useLocalPreference(
    "bwe:saved",
    [],
    (value) => validIds(value, bundledWallpapers),
  );
  const [serverLiked, setServerLiked] = useState([]);
  const [serverSaved, setServerSaved] = useState([]);
  const liked = apiMode ? serverLiked : likedLocal;
  const saved = apiMode ? serverSaved : savedLocal;
  const [theme, setTheme, themeUnavailable] = useLocalPreference(
    "bwe:theme",
    matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light",
    (value) => ["light", "dark"].includes(value),
  );
  const [selected, setSelected] = useState(null);
  const [activeCollection, setActiveCollection] = useState(null);
  const [profileOpen, setProfileOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [downloadingId, setDownloadingId] = useState(null);
  const [notice, setNotice] = useState(null);
  const [announcement, setAnnouncement] = useState("");
  const [detailLoading, setDetailLoading] = useState(false);
  const libraryPending = useRef(new Set());
  const detailRequest = useRef(0);
  const searchRef = useRef(null);
  const menuRef = useRef(null);
  const downloadLock = useRef(false);
  const mainHeading = useRef(null);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);
  useEffect(() => {
    document.title = `${titles[view]} | Bolu’s Wall Engine`;
  }, [view]);
  useEffect(() => {
    const onHash = () => {
      setView(currentView());
      setActiveCategory("All");
      setQuery("");
      setMobileOpen(false);
      setSelected(null);
      setNotice(null);
      detailRequest.current += 1;
      setDetailLoading(false);
      mainHeading.current?.focus();
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  useEffect(() => {
    if (!mobileOpen) return;
    const links = [...document.querySelectorAll("#site-navigation a")];
    const controls = [menuRef.current, ...links];
    links[0]?.focus();
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (event) => {
      if (event.key === "Escape") {
        setMobileOpen(false);
        menuRef.current?.focus();
      }
      if (event.key === "Tab") {
        const index = controls.indexOf(document.activeElement);
        event.preventDefault();
        controls[
          (index + (event.shiftKey ? -1 : 1) + controls.length) %
            controls.length
        ]?.focus();
      }
    };
    const desktop = matchMedia("(min-width: 801px)");
    const closeOnDesktop = () => {
      if (desktop.matches) setMobileOpen(false);
    };
    desktop.addEventListener("change", closeOnDesktop);
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = previousOverflow;
      desktop.removeEventListener("change", closeOnDesktop);
      window.removeEventListener("keydown", onKey);
    };
  }, [mobileOpen]);
  useEffect(() => {
    if (!apiMode || !signedIn) {
      setServerLiked([]);
      setServerSaved([]);
      return undefined;
    }
    let cancelled = false;
    sessionStore
      .loadLibrary()
      .then(({ liked: likes, saved: saves }) => {
        if (cancelled) return;
        setServerLiked(likes);
        setServerSaved(saves);
      })
      .catch(() => {
        if (cancelled) return;
        setNotice({
          text: "Your library could not be loaded. Reload the page to try again.",
        });
      });
    return () => {
      cancelled = true;
    };
  }, [signedIn, sessionState.user?.id]);
  useEffect(() => {
    if (!sessionState.error) return;
    setNotice({ text: sessionState.error });
    if (
      apiMode &&
      sessionState.status === "anonymous" &&
      /expired/i.test(sessionState.error)
    ) {
      setProfileOpen(true);
    }
  }, [sessionState.error, sessionState.status]);

  const localById = (id) =>
    wallpapers.find((wallpaper) => wallpaper.id === id);
  const collection = useMemo(() => {
    if (view === "liked")
      return wallpapers.filter((item) => liked.includes(item.id));
    if (view === "saved")
      return wallpapers.filter((item) => saved.includes(item.id));
    if (activeCollection)
      return wallpapers.filter((item) =>
        activeCollection.ids.includes(item.id),
      );
    return wallpapers;
  }, [view, liked, saved, activeCollection]);
  const filtered = useMemo(
    () =>
      filterWallpapers(collection, {
        category: activeCategory,
        query,
        sort,
      }),
    [collection, activeCategory, query, sort],
  );
  const resetFilters = () => {
    setQuery("");
    setActiveCategory("All");
    setSort("collection");
    setActiveCollection(null);
  };
  const scrollToResults = () => {
    document.getElementById("wallpaper-results")?.scrollIntoView({
      block: "start",
      behavior: matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "auto"
        : "smooth",
    });
  };
  const openCollection = (next) => {
    setQuery("");
    setActiveCategory("All");
    setSort("collection");
    setActiveCollection(next);
    setAnnouncement(`Showing the ${next.title} collection.`);
    requestAnimationFrame(scrollToResults);
  };
  const browseCategory = (name) => {
    setActiveCategory(name);
    requestAnimationFrame(scrollToResults);
  };
  const navigate = (next) => {
    resetFilters();
    setMobileOpen(false);
    setSelected(null);
    setNotice(null);
    detailRequest.current += 1;
    setDetailLoading(false);
    setView(next);
    location.hash = next;
    mainHeading.current?.focus();
    window.scrollTo({ top: 0, behavior: "instant" });
  };
  const updateLibrary = async (kind, slug) => {
    if (!signedIn) {
      setProfileOpen(true);
      setAnnouncement("Sign in to keep likes and saves in your account.");
      return;
    }
    const key = `${kind}:${slug}`;
    if (libraryPending.current.has(key)) return;
    libraryPending.current.add(key);
    const active =
      kind === "like" ? liked.includes(slug) : saved.includes(slug);
    try {
      const result =
        kind === "like"
          ? await sessionStore.setLike(slug, active)
          : await sessionStore.setSave(slug, active);
      const apply = (ids) =>
        result.active
          ? ids.includes(slug)
            ? ids
            : [...ids, slug]
          : ids.filter((id) => id !== slug);
      if (kind === "like") setServerLiked(apply);
      else setServerSaved(apply);
      setAnnouncement(
        result.active
          ? `Added to ${kind === "like" ? "liked" : "saved"} wallpapers.`
          : `Removed from ${kind === "like" ? "liked" : "saved"} wallpapers.`,
      );
    } catch (error) {
      setNotice({
        text:
          error?.status === 401
            ? "Your session expired. Sign in again to update your library."
            : `Couldn’t update your ${kind === "like" ? "likes" : "saved wallpapers"}. Please try again.`,
      });
    } finally {
      libraryPending.current.delete(key);
    }
  };
  const onLike = (id) => {
    if (apiMode) {
      void updateLibrary("like", id);
      return;
    }
    setLikedLocal((ids) => toggleId(ids, id));
    setAnnouncement(
      likedLocal.includes(id)
        ? "Removed from liked wallpapers."
        : "Added to liked wallpapers.",
    );
  };
  const onSave = (id) => {
    if (apiMode) {
      void updateLibrary("save", id);
      return;
    }
    setSavedLocal((ids) => toggleId(ids, id));
    setAnnouncement(
      savedLocal.includes(id)
        ? "Removed from saved wallpapers."
        : "Added to saved wallpapers.",
    );
  };
  const onDownload = async (wallpaper) => {
    if (downloadLock.current) return;
    downloadLock.current = true;
    setDownloadingId(wallpaper.id);
    setNotice({ text: `Preparing ${wallpaper.title}…` });
    try {
      if (apiMode) {
        const ticket = await apiClient.trackDownload(wallpaper.id);
        if (!ticket?.download_url) {
          throw new Error("The API did not return a download URL.");
        }
        await downloadFromUrl(ticket.download_url, wallpaper.title);
      } else {
        await downloadWallpaper(wallpaper);
      }
      setNotice({ text: `Download started: ${wallpaper.title}.` });
    } catch (error) {
      if (apiMode) {
        const text =
          error?.status === 429
            ? "Too many downloads right now. Wait a moment and try again."
            : error?.status === 404
              ? "That wallpaper is no longer available."
              : "The download could not be started. You can still open the source image.";
        setNotice({ text, url: wallpaper.fullUrl || wallpaper.url });
      } else {
        setNotice({
          text: "Direct download is unavailable. Open the source image, then use your browser’s Save image option.",
          url: wallpaper.url,
        });
      }
    } finally {
      downloadLock.current = false;
      setDownloadingId(null);
    }
  };
  const actionsFor = (wallpaper) => ({
    liked: liked.includes(wallpaper.id),
    saved: saved.includes(wallpaper.id),
    onLike,
    onSave,
    onDownload,
    downloadingId,
  });
  const openWallpaper = (wallpaper) => {
    setSelected(wallpaper);
    setNotice(null);
    if (!apiMode) return;
    const requestId = detailRequest.current + 1;
    detailRequest.current = requestId;
    setDetailLoading(true);
    apiClient
      .getWallpaper(wallpaper.id)
      .then((detail) => {
        if (detailRequest.current !== requestId) return;
        setSelected((current) =>
          current && current.id === wallpaper.id
            ? toUiWallpaperDetail(detail)
            : current,
        );
      })
      .catch(() => {
        if (detailRequest.current !== requestId) return;
        setNotice({
          text: "Full details for this wallpaper are unavailable. Showing the catalogue entry.",
        });
      })
      .finally(() => {
        if (detailRequest.current === requestId) setDetailLoading(false);
      });
  };
  const downloadNotice = notice && (
    <div className="download-notice" role="status">
      <div>
        {notice.text}
        {notice.url && (
          <a href={notice.url} target="_blank" rel="noopener noreferrer">
            Open source image <Icon name="external" size={14} />
          </a>
        )}
      </div>
      <button
        className="icon-button"
        aria-label="Dismiss download message"
        onClick={() => setNotice(null)}
      >
        <Icon name="close" size={17} />
      </button>
    </div>
  );
  const handleGoogleCredential = (idToken) => {
    if (!sessionStore || !googleClientId) return;
    void sessionStore.signInWithGoogle({ idToken, clientId: googleClientId });
  };
  const handleSignOut = () => {
    if (!sessionStore) return;
    void sessionStore.signOut();
    setAnnouncement("Signed out.");
  };
  const hasFilters = !!query || activeCategory !== "All" || !!activeCollection;
  const focusContent = (event) => {
    event.preventDefault();
    const content = document.getElementById("main-content");
    content.focus({ preventScroll: true });
    content.scrollIntoView({ block: "start" });
  };

  return (
    <div className="app">
      <a className="skip-link" href="#main-content" onClick={focusContent}>
        Skip to wallpapers
      </a>
      <Navigation
        view={view}
        onNavigate={navigate}
        likedCount={liked.length}
        savedCount={saved.length}
        storageLabel={
          apiMode
            ? signedIn
              ? "Synced to your account"
              : "Sign in to sync"
            : "Stored on this device"
        }
        mobileOpen={mobileOpen}
        onClose={() => {
          setMobileOpen(false);
          menuRef.current?.focus();
        }}
      />
      <div className="app-body">
        <header className="topbar">
          <button
            ref={menuRef}
            className="icon-button mobile-menu"
            aria-label={mobileOpen ? "Close navigation" : "Open navigation"}
            aria-expanded={mobileOpen}
            aria-controls="site-navigation"
            onClick={() => setMobileOpen(!mobileOpen)}
          >
            <Icon name={mobileOpen ? "close" : "menu"} />
          </button>
          <form
            className="search-form"
            inert={mobileOpen || undefined}
            role="search"
            onSubmit={(event) => {
              event.preventDefault();
              document
                .getElementById("wallpaper-results")
                ?.scrollIntoView({ block: "start" });
            }}
          >
            <Icon name="search" size={19} />
            <label className="sr-only" htmlFor="wallpaper-search">
              Search wallpapers
            </label>
            <input
              ref={searchRef}
              id="wallpaper-search"
              type="search"
              placeholder="Search wallpapers…"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
            {query ? (
              <button
                type="button"
                className="icon-button"
                aria-label="Clear search"
                onClick={() => {
                  setQuery("");
                  searchRef.current.focus();
                }}
              >
                <Icon name="close" size={16} />
              </button>
            ) : (
              <span className="search-hint">Find your next view</span>
            )}
          </form>
          <div className="topbar-actions" inert={mobileOpen || undefined}>
            <button
              className="icon-button theme-toggle"
              aria-label={`Switch to ${theme === "light" ? "dark" : "light"} theme`}
              onClick={() => setTheme(theme === "light" ? "dark" : "light")}
              title={`Switch to ${theme === "light" ? "dark" : "light"} theme`}
            >
              <Icon name={theme === "light" ? "moon" : "sun"} />
            </button>
            <span className="topbar-divider" />
            <button
              className="profile-button"
              onClick={() => setProfileOpen(true)}
              aria-label={
                apiMode
                  ? signedIn
                    ? "Open account"
                    : "Open sign-in"
                  : "Open local profile"
              }
            >
              <span className="avatar">
                {signedIn && sessionState.user?.displayName
                  ? sessionState.user.displayName.charAt(0).toUpperCase()
                  : "G"}
              </span>
              <span className="profile-label">
                {signedIn
                  ? sessionState.user?.displayName || "Signed in"
                  : "Guest"}
                <small>
                  {signedIn
                    ? "Synced library"
                    : apiMode
                      ? "Sign in to sync"
                      : "Local collection"}
                </small>
              </span>
            </button>
          </div>
        </header>
        <main
          className="main-content"
          inert={mobileOpen || undefined}
          id="main-content"
          tabIndex={-1}
        >
          <div
            className={`page-heading ${view === "home" ? "home-heading" : ""}`}
          >
            <div className="heading-main">
              <p className="eyebrow">
                {view === "home" ? "A WALLPAPER LIBRARY" : "WALLPAPER LIBRARY"}
              </p>
              <h1 ref={mainHeading} tabIndex={-1}>
                {titles[view]}
              </h1>
              <p className="heading-subtitle">{subtitles[view]}</p>
              {view === "home" && !hasFilters && (
                <div className="hero-actions">
                  <button className="button primary" onClick={scrollToResults}>
                    Explore the collection <Icon name="arrow" size={17} />
                  </button>
                  <button
                    className="hero-text-button"
                    onClick={() => navigate("categories")}
                  >
                    Browse categories <Icon name="arrow" size={15} />
                  </button>
                </div>
              )}
            </div>
            <div className="heading-aside">
              <span className="catalog-note">
                <span />{" "}
                {catalogue.loading
                  ? "Loading catalogue…"
                  : `${wallpapers.length} wallpapers · ${categories.length} categories`}
              </span>
              {view === "home" && !hasFilters && (
                <p className="hero-note">
                  {catalogue.mode === "api"
                    ? "Each entry shows its source and licence where the library records them."
                    : "Every added work carries its artist, license, and original source."}
                </p>
              )}
            </div>
          </div>
          {(themeUnavailable ||
            (!apiMode && (likesUnavailable || savesUnavailable))) && (
            <p className="storage-warning" role="status">
              Browser storage is unavailable or was reset. Your preferences may
              last only for this visit.
            </p>
          )}
          {view === "home" &&
            !hasFilters &&
            !catalogue.loading &&
            !catalogue.error &&
            featured.length === 3 && (
            <section
              className="featured-section"
              aria-labelledby="featured-title"
            >
              <div className="section-heading editorial-heading">
                <div>
                  <p className="section-kicker">
                    {catalogue.mode === "api" ? "MOST DOWNLOADED" : "EDITOR’S PICKS"}
                  </p>
                  <h2 id="featured-title">In the spotlight</h2>
                  <p className="section-intro">
                    {catalogue.mode === "api"
                      ? "The three most-downloaded wallpapers in the library."
                      : "Three images worth pausing on this week."}
                  </p>
                </div>
                <a
                  className="text-link"
                  href="#explore"
                  onClick={(event) => {
                    event.preventDefault();
                    navigate("explore");
                  }}
                >
                  Explore all <Icon name="arrow" size={16} />
                </a>
              </div>
              <div className="featured-grid">
                {featured.map((wallpaper, index) => (
                  <button
                    className="featured-card"
                    key={wallpaper.id}
                    onClick={() => openWallpaper(wallpaper)}
                    aria-label={`Featured: ${wallpaper.title}`}
                  >
                    <WallpaperImage wallpaper={wallpaper} eager />
                    <span className="featured-caption">
                      <span>
                        <small>{wallpaper.category}</small>
                        <strong>{wallpaper.title}</strong>
                      </span>
                      <span className="featured-arrow">
                        <Icon name="arrow" size={18} />
                      </span>
                    </span>
                    <span className="feature-index">0{index + 1}</span>
                  </button>
                ))}
              </div>
            </section>
          )}
          {view === "home" &&
            !hasFilters &&
            !catalogue.loading &&
            !catalogue.error && (
            <>
              <section
                className="editorial-section new-section"
                aria-labelledby="new-title"
              >
                <div className="section-heading editorial-heading">
                  <div>
                    <p className="section-kicker">RECENTLY ADDED</p>
                    <h2 id="new-title">
                      {newToLibrary ? "New to the library" : "Recently added"}
                    </h2>
                    <p className="section-intro">
                      {newToLibrary
                        ? `${newToLibrary.ids.length} new works, each with a documented source and license.`
                        : "The latest published wallpapers, most recent first."}
                    </p>
                  </div>
                  {newToLibrary && (
                    <button
                      className="text-link"
                      onClick={() => openCollection(newToLibrary)}
                    >
                      View all {newToLibrary.ids.length}{" "}
                      <Icon name="arrow" size={16} />
                    </button>
                  )}
                </div>
                <div className="editorial-grid">
                  {recentAdditions.map((wallpaper) => (
                    <WallpaperCard
                      key={wallpaper.id}
                      wallpaper={wallpaper}
                      onOpen={openWallpaper}
                      {...actionsFor(wallpaper)}
                    />
                  ))}
                </div>
              </section>
              {collections.length > 0 && (
              <section
                className="editorial-section"
                aria-labelledby="collections-title"
              >
                <div className="section-heading editorial-heading">
                  <div>
                    <p className="section-kicker">CURATED</p>
                    <h2 id="collections-title">Collections</h2>
                    <p className="section-intro">
                      Loose threads through the library, grouped by mood rather
                      than metrics.
                    </p>
                  </div>
                  <span className="result-count">
                    {collections.length} collections
                  </span>
                </div>
                <div className="collection-grid">
                  {collections.map((entry, index) => {
                    const cover =
                      localById(entry.representative) ?? localById(entry.ids[0]);
                    return (
                      <button
                        key={entry.id}
                        className="collection-card"
                        onClick={() => openCollection(entry)}
                        aria-label={`Open collection ${entry.title}`}
                      >
                        <WallpaperImage wallpaper={cover} />
                        <span className="collection-shade" />
                        <span className="collection-caption">
                          <span className="collection-index">0{index + 1}</span>
                          <strong>{entry.title}</strong>
                          <small>{entry.description}</small>
                          <span className="collection-count">
                            {entry.ids.length} wallpapers{" "}
                            <Icon name="arrow" size={14} />
                          </span>
                        </span>
                      </button>
                    );
                  })}
                </div>
              </section>
              )}
              <section
                className="editorial-section category-strip-section"
                aria-labelledby="category-strip-title"
              >
                <div className="section-heading editorial-heading">
                  <div>
                    <p className="section-kicker">BROWSE</p>
                    <h2 id="category-strip-title">By category</h2>
                  </div>
                  <button
                    className="text-link"
                    onClick={() => navigate("categories")}
                  >
                    All categories <Icon name="arrow" size={16} />
                  </button>
                </div>
                <div className="category-strip">
                  {categories.map(({ name, count }) => (
                    <button
                      key={name}
                      className="category-strip-button"
                      onClick={() => browseCategory(name)}
                      aria-label={`Browse ${name}, ${count} wallpapers`}
                    >
                      <span>{name}</span>
                      <small>{count}</small>
                    </button>
                  ))}
                </div>
              </section>
            </>
          )}
          {view === "categories" && !catalogue.loading && !catalogue.error && (
            <section
              className="category-tiles"
              aria-label="Wallpaper categories"
            >
              {categories.map(({ name, count }) => {
                const representative = wallpapers.find(
                  (item) => item.category === name,
                );
                return (
                  <button
                    key={name}
                    className={`category-tile ${activeCategory === name ? "selected" : ""}`}
                    aria-pressed={activeCategory === name}
                    onClick={() =>
                      setActiveCategory(activeCategory === name ? "All" : name)
                    }
                  >
                    {representative && (
                      <WallpaperImage wallpaper={representative} />
                    )}
                    <span>
                      <strong>{name}</strong>
                      <small>{count} wallpapers</small>
                    </span>
                    <Icon name="arrow" size={18} />
                  </button>
                );
              })}
            </section>
          )}
          <section id="wallpaper-results" aria-labelledby="results-title">
            <div className="section-heading collection-heading">
              <div className="collection-heading-main">
                <div className="collection-title">
                  <h2 id="results-title">
                    {activeCollection
                      ? activeCollection.title
                      : view === "liked"
                        ? "Your likes"
                        : view === "saved"
                          ? "Your saved collection"
                          : "The collection"}
                  </h2>
                  <span className="result-count" role="status">
                    {filtered.length} wallpaper
                    {filtered.length !== 1 ? "s" : ""}
                  </span>
                </div>
                {activeCollection && (
                  <p className="collection-blurb">
                    {activeCollection.description}
                  </p>
                )}
              </div>
              <label className="sort-control">
                Sort by{" "}
                <select
                  aria-label="Sort wallpapers"
                  value={sort}
                  onChange={(event) => setSort(event.target.value)}
                >
                  <option value="collection">Collection order</option>
                  <option value="title">Title A–Z</option>
                </select>
              </label>
            </div>
            <div className="filter-bar">
              <div
                className="category-filters"
                role="group"
                aria-label="Filter by category"
              >
                {[
                  { name: "All", count: collection.length },
                  ...categories.map(({ name }) => ({
                    name,
                    count: collection.filter((item) => item.category === name)
                      .length,
                  })),
                ].map(({ name, count }) => (
                  <button
                    key={name}
                    className={`category-btn ${activeCategory === name ? "active" : ""}`}
                    aria-pressed={activeCategory === name}
                    onClick={() => setActiveCategory(name)}
                  >
                    {name === "All" ? "All wallpapers" : name}
                    <span>{count}</span>
                  </button>
                ))}
              </div>
              {hasFilters && (
                <button className="reset-button" onClick={resetFilters}>
                  Reset filters <Icon name="close" size={14} />
                </button>
              )}
            </div>
            {query.trim() && (
              <p className="search-summary">
                Results for <strong>“{query.trim()}”</strong>
                {activeCategory !== "All" && ` in ${activeCategory}`}
              </p>
            )}
            {!selected && downloadNotice}
            {catalogue.truncated &&
              !catalogue.loading &&
              !catalogue.error && (
                <p className="storage-warning" role="status">
                  Showing the first {wallpapers.length} of {catalogue.total}{" "}
                  wallpapers. Refine the search to narrow the catalogue.
                </p>
              )}
            {catalogue.loading ? (
              <p className="storage-warning" role="status">
                Loading the wallpaper catalogue…
              </p>
            ) : catalogue.error ? (
              <div className="storage-warning" role="alert">
                <p>{catalogue.error}</p>
                <button className="reset-button" onClick={catalogue.reload}>
                  Retry loading <Icon name="arrow" size={14} />
                </button>
              </div>
            ) : filtered.length > 0 ? (
              <div className="wallpaper-grid">
                {filtered.map((wallpaper) => (
                  <WallpaperCard
                    key={wallpaper.id}
                    wallpaper={wallpaper}
                    onOpen={openWallpaper}
                    {...actionsFor(wallpaper)}
                  />
                ))}
              </div>
            ) : (
              <div className="empty-state">
                <span className="empty-icon">
                  <Icon
                    name={
                      view === "liked"
                        ? "heart"
                        : view === "saved"
                          ? "bookmark"
                          : "search"
                    }
                    size={28}
                  />
                </span>
                <h3>
                  {hasFilters
                    ? "No wallpapers found"
                    : view === "liked"
                      ? "Your favorites start here"
                      : "Make room for inspiration"}
                </h3>
                <p>
                  {hasFilters
                    ? "Try a different search or category to find your next wallpaper."
                    : `Tap the ${view === "liked" ? "heart" : "bookmark"} on a wallpaper to add it to this collection.`}
                </p>
                <button
                  className="button primary"
                  onClick={
                    hasFilters ? resetFilters : () => navigate("explore")
                  }
                >
                  {hasFilters ? "Reset filters" : "Explore wallpapers"}
                  <Icon name="arrow" size={17} />
                </button>
              </div>
            )}
            {!catalogue.loading && !catalogue.error && filtered.length > 0 && (
              <div className="collection-end">
                <span />
                <p>You’re all caught up · {filtered.length} wallpapers</p>
                <span />
              </div>
            )}
          </section>
          <footer className="site-footer">
            <span>Bolu’s Wall Engine</span>
            <span>A personal wallpaper collection.</span>
            <a href="#main-content" onClick={focusContent}>
              Back to top ↑
            </a>
          </footer>
        </main>
      </div>
      <div className="sr-only" role="status">
        {announcement}
      </div>
      {selected && (
        <WallpaperDetail
          wallpaper={selected}
          catalog={wallpapers}
          onClose={() => setSelected(null)}
          onOpen={openWallpaper}
          downloadNotice={downloadNotice}
          detailLoading={detailLoading}
          libraryNote={
            apiMode
              ? signedIn
                ? "Likes and saves are stored in your account."
                : "Sign in to keep likes and saves in your account."
              : undefined
          }
          {...actionsFor(selected)}
        />
      )}
      {profileOpen && (
        <Modal
          titleId="profile-title"
          onClose={() => setProfileOpen(false)}
          className="profile-modal"
        >
          {apiMode ? (
            <div className="profile-content">
              <span className="avatar large">
                {signedIn && sessionState.user?.displayName
                  ? sessionState.user.displayName.charAt(0).toUpperCase()
                  : "G"}
              </span>
              <p className="eyebrow">{signedIn ? "SIGNED IN" : "ACCOUNT"}</p>
              <h2 id="profile-title">
                {signedIn
                  ? sessionState.user?.displayName || "Your account"
                  : "Sign in to sync"}
              </h2>
              {signedIn ? (
                <>
                  <p>
                    {sessionState.user?.email ||
                      "Your likes and saves follow your account."}
                  </p>
                  <div className="profile-stats">
                    <button
                      onClick={() => {
                        setProfileOpen(false);
                        navigate("liked");
                      }}
                    >
                      <strong>{liked.length}</strong>Liked wallpapers
                      <Icon name="arrow" size={17} />
                    </button>
                    <button
                      onClick={() => {
                        setProfileOpen(false);
                        navigate("saved");
                      }}
                    >
                      <strong>{saved.length}</strong>Saved wallpapers
                      <Icon name="arrow" size={17} />
                    </button>
                  </div>
                  <button className="reset-button" onClick={handleSignOut}>
                    Sign out <Icon name="close" size={14} />
                  </button>
                  <p className="detail-note">
                    Your session is kept in memory for this tab. Reloading the
                    page signs you out.
                  </p>
                </>
              ) : (
                <>
                  <p>
                    Sign in with Google to keep likes and saves in your
                    account. Browsing and downloads stay available without an
                    account.
                  </p>
                  <GoogleSignIn
                    clientId={googleClientId}
                    busy={sessionState.status === "authenticating"}
                    onCredential={handleGoogleCredential}
                    onError={(message) => setNotice({ text: message })}
                  />
                  <p className="detail-note">
                    The theme preference stays in this browser.
                  </p>
                </>
              )}
            </div>
          ) : (
            <div className="profile-content">
              <span className="avatar large">G</span>
              <p className="eyebrow">ON THIS DEVICE</p>
              <h2 id="profile-title">Your local collection</h2>
              <p>
                You’re browsing as a guest. Likes, saves, and your theme are
                stored in this browser, not in an online account.
              </p>
              <div className="profile-stats">
                <button
                  onClick={() => {
                    setProfileOpen(false);
                    navigate("liked");
                  }}
                >
                  <strong>{liked.length}</strong>Liked wallpapers
                  <Icon name="arrow" size={17} />
                </button>
                <button
                  onClick={() => {
                    setProfileOpen(false);
                    navigate("saved");
                  }}
                >
                  <strong>{saved.length}</strong>Saved wallpapers
                  <Icon name="arrow" size={17} />
                </button>
              </div>
              <p className="detail-note">
                Clearing browser data removes these preferences.
              </p>
            </div>
          )}
        </Modal>
      )}
    </div>
  );
}

export default App;
