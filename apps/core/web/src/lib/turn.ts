/**
 * Turning a list of events into the shape a message renders as.
 *
 * The same function runs on the live stream and on a reloaded message, which is what makes
 * "the server render is authoritative" true rather than merely intended: at `done` the client
 * throws away everything it drew optimistically and calls this again on the persisted list. If
 * the two disagreed, the answer would visibly change the moment it finished — so they are the
 * same code path over the same variants, and there is nothing for them to disagree about.
 *
 * It groups rather than transforms. Every event keeps its identity; this only decides how it is
 * drawn — as a row in the gutter, as prose, or as a card in the flow — and pairs a tool result
 * with the call that produced it.
 *
 * **A turn is one list, in event order.** That is the property everything else here serves. It
 * used to be two — every gutter row, then all the prose — which reads correctly only for the
 * turn that does its thinking up front. The moment she speaks, thinks again and speaks again,
 * the second thought was drawn *above* the sentence that prompted it, and the turn could not be
 * read downwards at all. So `blocks` is the render order: a run of consecutive gutter rows is
 * one block, and prose and cards sit between the runs where she put them.
 *
 * The same rule is why reasoning is broken into pieces rather than collected into one. Anything
 * a person can *see* closes the block in progress, so the thought after a tool call is a new row
 * below it rather than more text appended to a row above it.
 */

import type { AnyEvent, ChatEvent, ToolCallReady, ToolResultEvent } from './api/events';
import { isAsk, isEmotion } from './api/events';

/** A row in the activity gutter: something she did before or between speaking. */
export interface Activity {
	// No `permission`: a card is drawn in the flow where the call would have happened, never as
	// a gutter row, and `ActivityRow` has never had a branch for one. Listing it here made the
	// two unions overlap on a kind neither side produces, which is the sort of thing that is
	// only ever discovered by a bug.
	kind: 'skill' | 'tool' | 'thinking' | 'unknown';
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
	kind: 'prose' | 'emotion' | 'permission' | 'question';
	key: string;
	text?: string;
	event?: AnyEvent;
}

/** One run of consecutive gutter rows, drawn as a single bordered block. */
export interface Gutter {
	kind: 'gutter';
	key: string;
	rows: Activity[];
}

/** What a message renders, top to bottom. */
export type Block = Gutter | Inline;

export interface Turn {
	/** The render order: gutter runs, prose and cards interleaved as they happened. */
	blocks: Block[];
	/** Every gutter row, flattened. A view over `blocks`, for callers that want the count or the
	 * lot without walking runs. */
	activity: Activity[];
	/** Everything that renders in the flow of the answer, flattened. Also a view. */
	inline: Inline[];
	/** The one terminator. `null` while the turn is still running. */
	closed: Extract<ChatEvent, { type: 'turn_closed' }> | null;
	/** Calls waiting on a person. The composer is blocked while this is non-empty.
	 *
	 * Both kinds of waiting, because the composer's question is *may I type?* and the answer is
	 * the same either way. Which card is open is read off the variant. */
	awaiting: Array<
		| Extract<ChatEvent, { type: 'permission_required' }>
		| Extract<ChatEvent, { type: 'answer_required' }>
	>;
	/** Everything she reasoned across the whole turn, blocks and all. The gutter shows it in
	 * pieces; this is the one string, for anything that wants the lot. */
	thinking: string;
}

export function reduce(events: AnyEvent[]): Turn {
	// One list, in the order things happened. `activity` and `inline` are read back out of it at
	// the end rather than filled alongside — two lists that have to stay in step is exactly the
	// arrangement that produced the out-of-order gutter.
	const ordered: Array<Activity | Inline> = [];
	const activity: Activity[] = [];
	const inline: Inline[] = [];
	const awaiting: Turn['awaiting'] = [];
	const byCall = new Map<string, Activity>();
	const decided = new Set<string>();
	const emotions = new Set<string>();
	const asked = new Set<string>();

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
		ordered.push({ kind: 'prose', key: `prose-${proseAt}`, text: prose });
		prose = '';
	};

	/** A gutter row, after whatever she had already said.
	 *
	 * The flush is the fix: without it, prose written before a tool call and prose written after
	 * it merge into one block, and the row lands after both — so the call appears below the
	 * sentence it produced. Every gutter row goes through here for that reason. */
	const row = (item: Activity) => {
		flush();
		ordered.push(item);
		return item;
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
		row({
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
				row({ kind: 'skill', key, event });
				break;

			case 'tool_call_ready': {
				const call = event as ToolCallReady;
				settle();
				if (isEmotion(call)) {
					// An emotion renders where she called it, between paragraphs, because that
					// is where she meant it (ADR 3). It is not a gutter row, but it is on screen,
					// so reasoning either side of it is two thoughts rather than one.
					flush();
					ordered.push({ kind: 'emotion', key, event: call });
					emotions.add(call.id);
					break;
				}
				if (isAsk(call)) {
					// The question card is built from `answer_required`, which arrives right
					// after this. Letting the call land in the gutter too would draw the same
					// question twice, once as machinery and once as the thing she said.
					break;
				}
				byCall.set(call.id, row({ kind: 'tool', key, event: call }));
				break;
			}

			case 'tool_result': {
				const result = event as ToolResultEvent;
				const waiting = byCall.get(result.call_id);
				if (waiting) {
					waiting.result = result;
				} else if (asked.has(result.call_id)) {
					// The person's reply, shaped as this call's result so the model reads it as
					// one. On screen it is already on the card they typed it into.
				} else if (emotions.has(result.call_id)) {
					// The card *is* the record of an emotion, so a gutter row beside it would
					// draw the same thing twice. A failed one is different: an emotion she
					// showed and the system refused is exactly what openness means you get to
					// see, so that one keeps its row.
					if (!result.ok) {
						settle();
						row({ kind: 'tool', key, event: result });
					}
				} else {
					// A result whose call is not in this list -- half a turn, reloaded. Keeping
					// it beats hiding the one record that something actually ran.
					settle();
					row({ kind: 'tool', key, event: result });
				}
				break;
			}

			case 'permission_required': {
				const card = event as Extract<ChatEvent, { type: 'permission_required' }>;
				settle();
				flush();
				ordered.push({ kind: 'permission', key, event: card });
				awaiting.push(card);
				break;
			}

			case 'permission_decided':
				decided.add((event as { call_id: string }).call_id);
				break;

			case 'answer_required': {
				const card = event as Extract<ChatEvent, { type: 'answer_required' }>;
				settle();
				flush();
				ordered.push({ kind: 'question', key, event: card });
				awaiting.push(card);
				asked.add(card.call_id);
				break;
			}

			case 'answer_given':
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
				row({ kind: 'unknown', key, event });
		}
	}

	flush();
	settle(true);

	// Consecutive gutter rows become one block, so the hairline and the marks still read as a
	// group. A run ends the moment something she said lands, which is the whole point.
	const blocks: Block[] = [];
	for (const item of ordered) {
		if (isActivity(item)) {
			activity.push(item);
			const last = blocks.at(-1);
			if (last && last.kind === 'gutter') last.rows.push(item);
			else blocks.push({ kind: 'gutter', key: `gutter-${item.key}`, rows: [item] });
			continue;
		}
		inline.push(item);
		blocks.push(item);
	}

	return {
		blocks,
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

/** A gutter row rather than something she said.
 *
 * Discriminated on `kind`, which the two unions no longer share a value of. A second tag field
 * would be one more thing to keep in step, and TypeScript narrows this correctly.
 */
function isActivity(item: Activity | Inline): item is Activity {
	return !INLINE_KINDS.has(item.kind);
}

const INLINE_KINDS = new Set<string>(['prose', 'emotion', 'permission', 'question']);

/** Whether a card is still open, for a message rendered from the persisted list.
 *
 * Both kinds settle the same way — a `permission_decided` or an `answer_given` for that call —
 * because both exist precisely so a reloaded turn shows a settled card rather than live
 * controls. Inferring it from whether a result turned up later would be a rule about event
 * ordering living in the browser. */
export function isAnswered(events: AnyEvent[], callId: string): boolean {
	return events.some(
		(event) =>
			(event.type === 'permission_decided' || event.type === 'answer_given') &&
			(event as { call_id: string }).call_id === callId
	);
}

/** What a person typed into a question card, for a message rendered from the persisted list. */
export function replyTo(events: AnyEvent[], callId: string): string {
	const given = events.find(
		(event) => event.type === 'answer_given' && (event as { call_id: string }).call_id === callId
	);
	return given ? ((given as { text: string }).text ?? '') : '';
}
