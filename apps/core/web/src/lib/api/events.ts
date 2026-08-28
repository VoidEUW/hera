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

export interface ToolCallStarted {
	type: 'tool_call_started';
	id: string;
	name: string;
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

export interface AnswerRequired {
	type: 'answer_required';
	call_id: string;
	tool: string;
	question: string;
	/** Her stance while asking, from the same open vocabulary an emotion card draws on. Free
	 * text, so an unknown one renders generically. */
	kind: string;
}

export interface AnswerGiven {
	type: 'answer_given';
	call_id: string;
	text: string;
}

export interface TurnClosed {
	type: 'turn_closed';
	reason:
		| 'completed'
		| 'cancelled'
		| 'awaiting_permission'
		| 'awaiting_answer'
		| 'max_iterations'
		| 'failed';
	usage: { prompt_tokens: number; completion_tokens: number; total_tokens: number } | null;
	iterations: number;
	error: string;
}

export type ChatEvent =
	| TextDelta
	| ThinkingDelta
	| ToolCallStarted
	| ToolCallReady
	| SkillSelected
	| ToolResultEvent
	| PermissionRequired
	| PermissionDecided
	| AnswerRequired
	| AnswerGiven
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
	'tool_call_started',
	'tool_call_ready',
	'skill_selected',
	'tool_result',
	'permission_required',
	'permission_decided',
	'answer_required',
	'answer_given',
	'turn_closed'
]);

export function isKnown(event: AnyEvent): event is ChatEvent {
	return KNOWN.has(event.type);
}

/** The emotion tool, which renders as a card rather than as a gutter row (ADR 3). */
export const EMOTION_TOOL = 'hera__emotion';

/** The asking tool. Its call and its result are both drawn by the question card — the card is
 * built from `answer_required`, so letting the call and its eventual result also fall through
 * to the gutter would draw the same exchange three times. */
export const ASK_TOOL = 'hera__ask';

/** The skill tool. Reaching for a skill mid-task and being handed one before the turn are the
 * same thing to a reader, so they are drawn the same way — see `Scroll.svelte`. */
export const SKILL_TOOL = 'hera__skill';

/** Her own namespace, which is the only one this interface is allowed to recognise. */
export const HERA = 'hera__';

/** The name on either kind of call event, or `''` for anything else.
 *
 * Both `tool_call_started` and `tool_call_ready` are about the same call and carry the same
 * `name`, so every question of the form *is this call an X* has to accept both — otherwise the
 * emotion she announced draws a gutter row for a second and then turns into a card. */
function callName(event: AnyEvent): string {
	if (event.type !== 'tool_call_started' && event.type !== 'tool_call_ready') return '';
	return (event as { name?: string }).name ?? '';
}

export function isEmotion(event: AnyEvent): boolean {
	// A plain predicate rather than a type guard: the caller already knows it holds a call
	// event, and a guard would narrow the *negative* branch to `never`.
	return callName(event) === EMOTION_TOOL;
}

/** Whether this call is her asking the person something. */
export function isAsk(event: AnyEvent): boolean {
	return callName(event) === ASK_TOOL;
}

/** Whether this tool row is about a skill, by call or by result.
 *
 * Knowing these two names is not the same as recognising tools in general: `hera__*` is *her*
 * namespace, the four tools on it are shipped in this repository, and the interface already
 * draws one of them as a card. What it must not do is learn somebody else's server — that is
 * what makes an unfamiliar tool look broken next to a familiar one. */
export function isSkillTool(event: AnyEvent): boolean {
	if (event.type === 'tool_result') return (event as { tool?: string }).tool === SKILL_TOOL;
	return callName(event) === SKILL_TOOL;
}
