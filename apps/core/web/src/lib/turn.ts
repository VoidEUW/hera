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
	let prose = '';
	let index = 0;

	const flush = () => {
		if (!prose) return;
		inline.push({ kind: 'prose', key: `prose-${index}`, text: prose });
		prose = '';
	};

	for (const event of events) {
		index += 1;
		const key = `${event.type}-${index}`;

		switch (event.type) {
			case 'text_delta':
				prose += (event as { text: string }).text;
				break;

			case 'thinking_delta':
				// Collapsed into one gutter row however many fragments arrived. Reasoning is
				// shown differently from prose and never mixed into it.
				thinking += (event as { text: string }).text;
				break;

			case 'skill_selected':
				activity.push({ kind: 'skill', key, event });
				break;

			case 'tool_call_ready': {
				const call = event as ToolCallReady;
				if (isEmotion(call)) {
					// An emotion renders where she called it, between paragraphs, because that
					// is where she meant it (ADR 3).
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
					if (!result.ok) activity.push({ kind: 'tool', key, event: result });
				} else {
					// A result whose call is not in this list -- half a turn, reloaded. Keeping
					// it beats hiding the one record that something actually ran.
					activity.push({ kind: 'tool', key, event: result });
				}
				break;
			}

			case 'permission_required': {
				const card = event as Extract<ChatEvent, { type: 'permission_required' }>;
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
				activity.push({ kind: 'unknown', key, event });
		}
	}

	flush();

	if (thinking) {
		activity.unshift({
			kind: 'thinking',
			key: 'thinking',
			event: { type: 'thinking_delta', text: thinking }
		});
	}

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
