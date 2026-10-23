import type { MetadataRoute } from "next";

// Lets phones and tablets add the app to the home screen and open it full screen (SPEC 2: PWA).
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Shokogi Boards",
    short_name: "Shokogi",
    description: "Board rentals for the Shokogi surf club",
    start_url: "/",
    display: "standalone",
    background_color: "#f4f5f7",
    theme_color: "#0b1220",
    icons: [
      { src: "/icons/192.png", sizes: "192x192", type: "image/png" },
      { src: "/icons/512.png", sizes: "512x512", type: "image/png" },
      { src: "/icons/maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
