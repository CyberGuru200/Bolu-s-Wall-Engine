import { useState } from "react";
import Icon from "./Icon";

export default function WallpaperImage({
  wallpaper,
  eager = false,
  className = "",
}) {
  const [state, setState] = useState("loading");
  return (
    <span
      className={`wallpaper-image ${className} image-${state}`}
      style={
        wallpaper.width && wallpaper.height
          ? { aspectRatio: `${wallpaper.width} / ${wallpaper.height}` }
          : undefined
      }
    >
      {state !== "error" ? (
        <img
          src={wallpaper.url}
          alt={wallpaper.title}
          loading={eager ? "eager" : "lazy"}
          decoding="async"
          onLoad={() => setState("loaded")}
          onError={() => setState("error")}
        />
      ) : (
        <span className="image-fallback">
          <Icon name="image" size={28} />
          <span>Preview unavailable</span>
          <small>{wallpaper.title}</small>
        </span>
      )}
    </span>
  );
}
