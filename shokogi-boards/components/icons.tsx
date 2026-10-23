// Line icons from the prototype: 24 px viewBox; stroke, caps and joins are set in globals.css.
const PATHS = {
  dash: '<rect x="3" y="3" width="7" height="9"/><rect x="14" y="3" width="7" height="5"/><rect x="14" y="12" width="7" height="9"/><rect x="3" y="16" width="7" height="5"/>',
  users: '<circle cx="9" cy="8" r="4"/><path d="M2 21v-1a5 5 0 0 1 5-5h4a5 5 0 0 1 5 5v1"/><path d="M16 4a4 4 0 0 1 0 8M22 21v-1a5 5 0 0 0-3-4.6"/>',
  board: '<path d="M12 2c3 3 4.5 8 4.5 11.5S14.5 22 12 22s-4.5-5-4.5-8.5S9 5 12 2z"/><path d="M12 7v11"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  sheet: '<rect x="3" y="3" width="18" height="18"/><path d="M3 9h18M3 15h18M9 3v18"/>',
  download: '<path d="M12 3v12M7 10l5 5 5-5M4 21h16"/>',
  upload: '<path d="M12 21V9M7 14l5-5 5 5M4 3h16"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  clip: '<rect x="5" y="4" width="14" height="17"/><path d="M9 2h6v4H9zM9 11h6M9 15h6"/>',
  sliders: '<path d="M4 6h9M17 6h3M4 12h3M11 12h9M4 18h11M19 18h1"/><rect x="13" y="4" width="4" height="4"/><rect x="7" y="10" width="4" height="4"/><rect x="15" y="16" width="4" height="4"/>',
  x: '<path d="M6 6l12 12M18 6L6 18"/>',
  cal: '<rect x="3" y="5" width="18" height="16"/><path d="M3 10h18M8 3v4M16 3v4"/>',
  left: '<path d="M15 6l-6 6 6 6"/>',
  right: '<path d="M9 6l6 6-6 6"/>',
  phone: '<path d="M5 3h4l2 5-2.5 1.5a11 11 0 0 0 6 6L16 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 5a2 2 0 0 1 2-2z"/>',
};

export type IconName = keyof typeof PATHS;

export function Icon({ name }: { name: IconName }) {
  return <svg viewBox="0 0 24 24" aria-hidden="true" dangerouslySetInnerHTML={{ __html: PATHS[name] }} />;
}
