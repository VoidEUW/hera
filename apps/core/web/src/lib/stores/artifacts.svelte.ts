/**
 * Which artifact the drawer is showing, and when everything drawing one should look again.
 *
 * A store rather than props, and the reason is the shape of the feature: the card that opens the
 * drawer can be five messages up the transcript, and threading a callback from the page through
 * `Message` and into a card would put an artifact-shaped hole in two components that have nothing
 * to do with artifacts.
 *
 * `version` is the other half. An artifact has **one current state everywhere it appears** (ADR
 * 13), so an edit in turn nine changes what the card in turn four draws — but nothing tells that
 * card its file moved underneath it. Bumping a counter when an `artifact_*` result lands is what
 * makes every view of it re-fetch, and it is a counter rather than a name because the drawer, the
 * file bar and each card all want to know the same thing: *something published changed*.
 */

import type { Artifact } from '$lib/api/events';

/** Her tools that touch something published. Two prefixes rather than one, because drawing a
 * diagram is its own tool and a file it made is still a file the drawer and the cards are
 * showing — a diagram missing from this list is one whose edit nothing re-fetches. */
const PUBLISHING_TOOLS = ['hera__artifact_', 'hera__diagram_'];

class Artifacts {
	/** The chat whose drawer is open, or `null` when it is closed. */
	chatId = $state<string | null>(null);
	/** Which artifact is shown. `null` with a `chatId` set means *pick one for me*: `ArtifactDrawer`
	 * fills it in with the most recently written file as soon as its listing lands, so nobody has
	 * to know which one that is in order to open the panel. It stays `null` only when there is
	 * genuinely nothing published, which is the one case the empty copy is about. */
	name = $state<string | null>(null);
	/** Showing the code of the open artifact instead of the drawn thing. Belongs to the file: it
	 * is cleared whenever another one is chosen, so every file opens drawn. */
	source = $state(false);
	/** Bumped whenever something published may have changed. Read by anything that fetched. */
	version = $state(0);
	/** The Edit switch of the open file: a text box over the source instead of the drawn thing. */
	editing = $state(false);
	/** What has been typed and not saved, or `null` when the file on screen is the file on disk.
	 * Kept here and not in the view so it survives the view being rebuilt — switching Preview and
	 * Source, or the file being re-read after a save — and so the header's Save can see it. */
	draft = $state<string | null>(null);
	/** The save in flight. */
	saving = $state(false);
	/** A leave that was held back because the draft would be lost; the drawer asks, and runs
	 * this on a yes. */
	asking = $state<(() => void) | null>(null);

	get dirty(): boolean {
		return this.draft !== null;
	}

	/** Record an edit. `base` is the text on disk: typing it back to what it was is not a change,
	 * and a Save that lit up for nothing would be a button that lies. */
	edit(text: string, base: string) {
		this.draft = text === base ? null : text;
	}

	/** Run `leave` now, or — if it would throw an unsaved edit away — after the person says so.
	 * What every control that closes the drawer or changes the file goes through. */
	ask(leave: () => void) {
		if (this.dirty) this.asking = leave;
		else leave();
	}

	/** The person said to throw the edit away. */
	discard() {
		const leave = this.asking;
		this.asking = null;
		this.draft = null;
		this.editing = false;
		leave?.();
	}

	get open(): boolean {
		return this.chatId !== null;
	}

	show(chatId: string, name: string | null = null) {
		this.chatId = chatId;
		if (name !== this.name) {
			this.source = false;
			this.#drop();
		}
		this.name = name;
	}

	close() {
		this.chatId = null;
		this.name = null;
		this.source = false;
		this.#drop();
	}

	/** A draft belongs to the file it was typed in. */
	#drop() {
		this.draft = null;
		this.editing = false;
		this.asking = null;
	}

	/** Forget an open drawer that belongs to a conversation nobody is looking at any more.
	 *
	 * Called when a chat screen opens. Without it, walking from one conversation to another
	 * leaves the previous one's page on screen beside a transcript it has nothing to do with. */
	leave() {
		this.close();
	}

	/** Note that a turn touched something published.
	 *
	 * Deliberately blunt about *which* call counts: any result from one of her artifact tools
	 * does, including a read. Working out which of them really changed a file would mean this
	 * store learning what each tool does, and being wrong in this direction costs one extra fetch
	 * of a file that is already in a cache.
	 *
	 * It is **not** blunt about being called twice. The caller is an effect over the event list
	 * of the turn in flight, so it re-runs on every fragment that arrives and offers the same
	 * result again and again; `#seen` is what makes that idempotent. It is a plain `Set` and not
	 * `$state`, deliberately — reading reactive state here would make every reader of `version`
	 * a dependency of the thing that writes it.
	 *
	 * `published` is what she just made, when this call was the one that made it. A page opens
	 * beside the conversation as it lands, because the next thing anybody does with a page is
	 * look at it, and hunting for the **Open** on a card that is still arriving is a step nobody
	 * wants. A figure marked `inline` — which a diagram is unless the call asked for it beside the
	 * conversation — does **not** open: it is already on screen where she
	 * drew it, and taking half the width away from the sentence it explains is the opposite of
	 * what `inline` asked for. The caller reads the turn in flight, so this happens while she is
	 * publishing and never on a reload — reopening for a conversation that already had published
	 * artifacts before this visit is the page's own job (`+page.svelte`'s `reopenIfPublished`),
	 * not this method's. That one defers to this one: a drawer already open on the file she just
	 * made is never reset to nothing chosen. */
	noticed(chatId: string | null, callId: string, tool: string, published: Artifact | null) {
		const hers = PUBLISHING_TOOLS.some((prefix) => tool.startsWith(prefix));
		if (!hers || this.#seen.has(callId)) return;
		this.#seen.add(callId);
		this.version += 1;
		if (chatId && published && !published.inline) this.show(chatId, published.name);
	}

	#seen = new Set<string>();
}

export const artifacts = new Artifacts();
