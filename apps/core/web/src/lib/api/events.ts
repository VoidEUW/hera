/**
 * The event union, as the browser sees it.
 *
 * A mirror of `hera_chats.events.ChatEvent`, discriminated on `type` exactly as the server
 * discriminates on it. This file is the *only* place the interface describes what a turn is
 * made of, and every component below renders one variant of it.
 *
 * **Nothing here parses anything.** That is the rule the whole system is shaped around: the
 * previous version of Hera had a parser on the server and a second one in the browser that had
 * to stay byte-compatible with it forever. A new kind of thing a turn can contain is one new
 * variant here and one new branch where it renders — never a regular expression.
 */

export interface TextDelta {
	type: 'text_delta';
	text: string;
}

export interface ThinkingDelta {
	type: 'thinking_delta';
	text: string;
}

export interface ToolCallReady {
	type: 'tool_call_ready';
	id: string;
	name: string;
	arguments: Record<string, unknown>;
	raw_arguments: string;
	parse_error: string | null;
}

export interface SkillSelected {
	type: 'skill_selected';
	skill: string;
	/** Why she has it. The gutter shows "she always has this" apart from "she went and found
	 * this", and this is the field that difference is read from. */
	reason: 'pinned' | 'slash' | 'retrieved';
	score: number | null;
}

export interface ToolResultEvent {
	type: 'tool_result';
	call_id: string;
	tool: string;
	ok: boolean;
	/** A plain string rather than a closed set, so a failure kind added on the server reads
	 * through to here as itself instead of breaking the render. */
	failure: string | null;
	text: string;
	structured: unknown;
	blocks: Array<Record<string, unknown>>;
	duration_ms: number;
}

export interface PermissionRequired {
	type: 'permission_required';
	call_id: string;
	tool: string;
	arguments: Record<string, unknown>;
	reason: string;
}

export interface PermissionDecided {
	type: 'permission_decided';
	call_id: string;
	allowed: boolean;
	remembered: boolean;
}

export interface TurnClosed {
	type: 'turn_closed';
	reason: 'completed' | 'cancelled' | 'awaiting_permission' | 'max_iterations' | 'failed';
	usage: { prompt_tokens: number; completion_tokens: number; total_tokens: number } | null;
	iterations: number;
	error: string;
}

export type ChatEvent =
	| TextDelta
	| ThinkingDelta
	| ToolCallReady
	| SkillSelected
	| ToolResultEvent
	| PermissionRequired
	| PermissionDecided
	| TurnClosed;

/** An event the server sent that this build does not know about.
 *
 * Kept as a type rather than thrown away, because a variant added by a newer server must
 * **degrade visibly** rather than silently: an interface that drops what it does not recognise
 * is one where a missing feature and a broken one look identical. */
export interface UnknownEvent {
	type: string;
	[key: string]: unknown;
}

export type AnyEvent = ChatEvent | UnknownEvent;

const KNOWN = new Set([
	'text_delta',
	'thinking_delta',
	'tool_call_ready',
	'skill_selected',
	'tool_result',
	'permission_required',
	'permission_decided',
	'turn_closed'
]);

export function isKnown(event: AnyEvent): event is ChatEvent {
	return KNOWN.has(event.type);
}

/** The emotion tool, which renders as a card rather than as a gutter row (ADR 3). */
export const EMOTION_TOOL = 'hera__emotion';

/** The skill tool. Reaching for a skill mid-task and being handed one before the turn are the
 * same thing to a reader, so they are drawn the same way — see `Scroll.svelte`. */
export const SKILL_TOOL = 'hera__skill';

/** Her own namespace, which is the only one this interface is allowed to recognise. */
export const HERA = 'hera__';

export function isEmotion(event: AnyEvent): boolean {
	// A plain predicate rather than a type guard: the caller already knows it holds a
	// ToolCallReady, and a guard would narrow the *negative* branch to `never`.
	return event.type === 'tool_call_ready' && (event as ToolCallReady).name === EMOTION_TOOL;
}

/** Whether this tool row is about a skill, by call or by result.
 *
 * Knowing these two names is not the same as recognising tools in general: `hera__*` is *her*
 * namespace, the four tools on it are shipped in this repository, and the interface already
 * draws one of them as a card. What it must not do is learn somebody else's server — that is
 * what makes an unfamiliar tool look broken next to a familiar one. */
export function isSkillTool(event: AnyEvent): boolean {
	if (event.type === 'tool_call_ready') return (event as ToolCallReady).name === SKILL_TOOL;
	if (event.type === 'tool_result') return (event as { tool?: string }).tool === SKILL_TOOL;
	return false;
}
