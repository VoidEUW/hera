/**
 * What a project's colour is allowed to be.
 *
 * A **token name**, not a hex. The interface has two themes, and a colour picked against the
 * dark ground — where `--brass` is `#d9ae52` — is illegible on vellum, where it is `#8a6a1c`.
 * Storing the name lets each theme resolve it to its own value, which is the same reason
 * nothing else in this codebase writes a literal colour outside `app.css`.
 *
 * Three, and they are the three the palette already has (`docs/frontend.md` § Colour). This is
 * deliberately not a colour wheel: an arbitrary hue chosen per project would put colours in the
 * rail that belong to no palette and read as somebody else's application. `''` is the ordinary
 * colour and is what every project starts as.
 */

export const PROJECT_COLOURS = ['', 'brass', 'laurel', 'pomegranate'] as const;

export type ProjectColour = (typeof PROJECT_COLOURS)[number];

/** The CSS variable a colour name resolves to, or `null` for the ordinary colour.
 *
 * Unknown names resolve to `null` rather than throwing. A project carrying a colour this build
 * does not know about — written by a newer version, or edited into the database by hand — should
 * draw as an ordinary project, not break the rail it appears in.
 */
export function colourOf(name: string): string | null {
	return name && (PROJECT_COLOURS as readonly string[]).includes(name) ? `var(--${name})` : null;
}
