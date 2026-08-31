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

const ARTIFACT_TOOL = 'hera__artifact_';

class Artifacts {
	/** The chat whose drawer is open, or `null` when it is closed. */
	chatId = $state<string | null>(null);
	/** Which artifact is shown. `null` with a `chatId` set means the file bar with nothing
	 * chosen — which is what the header control opens when the last one was deleted with its
	 * chat, and what a conversation with several of them opens into. */
	name = $state<string | null>(null);
	/** Bumped whenever something published may have changed. Read by anything that fetched. */
	version = $state(0);

	get open(): boolean {
		return this.chatId !== null;
	}

	show(chatId: string, name: string | null = null) {
		this.chatId = chatId;
		this.name = name;
	}

	close() {
		this.chatId = null;
		this.name = null;
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
	 * wants. A figure she marked `inline` does **not** open: it is already on screen where she
	 * drew it, and taking half the width away from the sentence it explains is the opposite of
	 * what `inline` asked for. The caller reads the turn in flight, so this happens while she is
	 * publishing and never on a reload — coming back to a conversation leaves you where you
	 * left it. */
	noticed(chatId: string | null, callId: string, tool: string, published: Artifact | null) {
		if (!tool.startsWith(ARTIFACT_TOOL) || this.#seen.has(callId)) return;
		this.#seen.add(callId);
		this.version += 1;
		if (chatId && published && !published.inline) this.show(chatId, published.name);
	}

	#seen = new Set<string>();
}

export const artifacts = new Artifacts();
