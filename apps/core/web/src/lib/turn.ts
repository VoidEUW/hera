/**
 * Turning a list of events into the shape a message renders as.
 *
 * The same function runs on the live stream and on a reloaded message, which is what makes
 * "the server render is authoritative" true rather than merely intended: at `done` the client
 * throws away everything it drew optimistically and calls this again on the persisted list. If
 * the two disagreed, the answer would visibly change the moment it finished — so they are the
 * same code path over the same variants, and there is nothing for them to disagree about.
 *
 * It groups rather than transforms. Every event keeps its identity; this only decides which of
 * three places it belongs in — the gutter above the prose, the prose itself, or a card in the
 * flow — and pairs a tool result with the call that produced it.
 *
 * The gutter is in **event order**, and that is the whole reason reasoning is broken into
 * blocks rather than collected into one. A turn that thinks, calls a tool, reads the result and
 * thinks again is a trace you follow downwards; folding both stretches of reasoning into a
 * single row at the top means the second half of her thinking appears above the call that
 * caused it, and the only way to read the turn in order is to scroll back up to a block that
 * has grown since you last looked at it.
 */

import type { AnyEvent, ChatEvent, ToolCallReady, ToolResultEvent } from './api/events';
import { isEmotion } from './api/events';

/** A row in the activity gutter: something she did before or between speaking. */
export interface Activity {
	kind: 'skill' | 'tool' | 'thinking' | 'permission' | 'unknown';
	key: string;
	event: AnyEvent;
	/** The result, for a tool row whose call has come back. Absent while it is still running,
	 * which is exactly what the row shows as "running". */
	result?: ToolResultEvent;
	/** Set on a block of reasoning that was **still open when the event list ran out** — she was
	 * mid-thought and nothing had interrupted her yet.
	 *
	 * Not the same as "the turn is streaming", and it cannot be: a persisted turn also ends
	 * while a block is open, because `turn_closed` draws nothing and so does not close one. The
	 * caller pairs this with whether the stream is actually live. */
	live?: boolean;
}

/** Something that renders in the flow of the answer, where she put it. */
export interface Inline {
	kind: 'prose' | 'emotion' | 'permission';
	key: string;
	text?: string;
	event?: AnyEvent;
}

export interface Turn {
	activity: Activity[];
	inline: Inline[];
	/** The one terminator. `null` while the turn is still running. */
	closed: Extract<ChatEvent, { type: 'turn_closed' }> | null;
	/** Calls waiting on a person. The composer is blocked while this is non-empty. */
	awaiting: Extract<ChatEvent, { type: 'permission_required' }>[];
	/** Everything she reasoned across the whole turn, blocks and all. The gutter shows it in
	 * pieces; this is the one string, for anything that wants the lot. */
	thinking: string;
}

export function reduce(events: AnyEvent[]): Turn {
	const activity: Activity[] = [];
	const inline: Inline[] = [];
	const awaiting: Extract<ChatEvent, { type: 'permission_required' }>[] = [];
	const byCall = new Map<string, Activity>();
	const decided = new Set<string>();
	const emotions = new Set<string>();

	let closed: Turn['closed'] = null;
	let thinking = '';
	let thought = '';
	let prose = '';
	let index = 0;

	// Where each run started, which is what its key is built from. Deliberately *not* the index
	// at the moment it is closed: a block still being written closes at the end of the list, so
	// its key would change with every fragment that arrived, Svelte would treat each one as a
	// different row, and the component would be destroyed and rebuilt a few times a second.
	// Everything it holds goes with it -- which is why a thought could not be opened while she
	// was still having it. Keyed on the start, a block is the same row from its first token.
	let proseAt = 0;
	let thoughtAt = 0;

	const flush = () => {
		if (!prose) return;
		inline.push({ kind: 'prose', key: `prose-${proseAt}`, text: prose });
		prose = '';
	};

	/** Close the block of reasoning in progress and put it in the gutter where it happened.
	 *
	 * Called before anything a person can *see* lands, which is what keeps the trace linear: she
	 * thinks, calls a tool, reads the result and thinks again, and the second block of reasoning
	 * is a second row *below* the call rather than more text appended to the first one. Reading
	 * a turn top to bottom used to mean scrolling back up to a block that had grown since.
	 *
	 * "Something visible" and not "something in the gutter": prose between two stretches of
	 * reasoning is a seam too, and running them together produced sentences that collided —
	 * `…I can answer now.Nothing more to add…` — with nothing on screen to explain the join.
	 * Bookkeeping that draws nothing (`permission_decided`, `turn_closed`) leaves a block alone.
	 *
	 * A no-op when there is no reasoning in progress, so callers do not have to check. */
	const settle = (last = false) => {
		if (!thought) return;
		activity.push({
			kind: 'thinking',
			key: `thinking-${thoughtAt}`,
			event: { type: 'thinking_delta', text: thought },
			live: last
		});
		thought = '';
	};

	for (const event of events) {
		index += 1;
		const key = `${event.type}-${index}`;

		switch (event.type) {
			case 'text_delta':
				settle();
				if (!prose) proseAt = index;
				prose += (event as { text: string }).text;
				break;

			case 'thinking_delta':
				// Fragments are collapsed into one row, but only the ones with nothing between
				// them. Reasoning is shown differently from prose and never mixed into it.
				if (!thought) thoughtAt = index;
				thought += (event as { text: string }).text;
				thinking += (event as { text: string }).text;
				break;

			case 'skill_selected':
				settle();
				activity.push({ kind: 'skill', key, event });
				break;

			case 'tool_call_ready': {
				const call = event as ToolCallReady;
				settle();
				if (isEmotion(call)) {
					// An emotion renders where she called it, between paragraphs, because that
					// is where she meant it (ADR 3). It is not a gutter row, but it is on screen,
					// so reasoning either side of it is two thoughts rather than one.
					flush();
					inline.push({ kind: 'emotion', key, event: call });
					emotions.add(call.id);
					break;
				}
				const row: Activity = { kind: 'tool', key, event: call };
				activity.push(row);
				byCall.set(call.id, row);
				break;
			}

			case 'tool_result': {
				const result = event as ToolResultEvent;
				const row = byCall.get(result.call_id);
				if (row) {
					row.result = result;
				} else if (emotions.has(result.call_id)) {
					// The card *is* the record of an emotion, so a gutter row beside it would
					// draw the same thing twice. A failed one is different: an emotion she
					// showed and the system refused is exactly what openness means you get to
					// see, so that one keeps its row.
					if (!result.ok) {
						settle();
						activity.push({ kind: 'tool', key, event: result });
					}
				} else {
					// A result whose call is not in this list -- half a turn, reloaded. Keeping
					// it beats hiding the one record that something actually ran.
					settle();
					activity.push({ kind: 'tool', key, event: result });
				}
				break;
			}

			case 'permission_required': {
				const card = event as Extract<ChatEvent, { type: 'permission_required' }>;
				settle();
				flush();
				inline.push({ kind: 'permission', key, event: card });
				awaiting.push(card);
				break;
			}

			case 'permission_decided':
				decided.add((event as { call_id: string }).call_id);
				break;

			case 'turn_closed':
				closed = event as Turn['closed'];
				break;

			default:
				// A variant this build has never heard of. Shown as a gutter row saying so,
				// because an interface that drops what it does not recognise makes a missing
				// feature and a broken one look identical.
				settle();
				activity.push({ kind: 'unknown', key, event });
		}
	}

	flush();
	settle(true);

	return {
		activity,
		inline,
		closed,
		// A card that has been answered is no longer waiting, even though both events are in
		// the list -- which is why `permission_decided` is persisted at all. Working it out
		// from whether a result turned up later would be a rule about event ordering living
		// in the browser.
		awaiting: awaiting.filter((card) => !decided.has(card.call_id)),
		thinking
	};
}

/** Whether a card is still open, for a message rendered from the persisted list. */
export function isAnswered(events: AnyEvent[], callId: string): boolean {
	return events.some(
		(event) =>
			event.type === 'permission_decided' && (event as { call_id: string }).call_id === callId
	);
}
