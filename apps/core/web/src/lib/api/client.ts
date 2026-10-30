/**
 * The API, typed.
 *
 * One origin, no CORS, no base URL to configure: the interface is served by the application it
 * talks to (ADR 6). Every function here is a thin wrapper whose only job is to turn a non-2xx
 * into an error with the server's own `detail` in it — a fetch that silently returns an error
 * body as if it were data is the bug this file exists to prevent.
 */

import type { Attachment } from '$lib/attachments';
import type { AnyEvent } from './events';

export const API = '/api/v1';

export interface Profile {
	id: string;
	slug: string;
	name: string;
	description: string;
	is_default: boolean;
	disabled_regions: string[];
	overrides: Record<string, string>;
	traits: Record<string, string | number | boolean>;
	pinned_skills: string[];
}

export interface Project {
	id: string;
	slug: string;
	name: string;
	instructions: string;
	pinned_skills: string[];
	default_profile_id: string | null;
	/** Which agent a new chat here starts with, once there are agents. Read-only: nothing writes
	 * it in v0.2, and the project screen draws the control disabled rather than absent. */
	default_agent_id: string | null;
	/** A palette token name, or empty for the ordinary colour. Not a hex — see `$lib/projects`. */
	color: string;
	archived: boolean;
}

/** What a project PATCH may carry.
 *
 * Not `Partial<Project>`: `id`, `slug` and `default_agent_id` are not writable, and spreading a
 * whole project into a patch is how a stale tab overwrites a field somebody else just changed.
 * A key left out means *leave it*, on every field including `default_profile_id` — sending that
 * one as `null` is what clears it.
 */
export interface ProjectPatch {
	name?: string;
	instructions?: string;
	pinned_skills?: string[];
	default_profile_id?: string | null;
	color?: string;
	archived?: boolean;
}

export interface Chat {
	id: string;
	title: string;
	project_id: string | null;
	profile_id: string | null;
	pinned: boolean;
	/** Skills switched on for this conversation, ahead of the profile's and the project's. */
	pinned_skills: string[];
	created_at: string;
	last_message_at: string | null;
}

export interface ArtifactSummary {
	name: string;
	bytes: number;
	modified_at: string;
}

export interface ArtifactContent {
	name: string;
	bytes: number;
	/** The file as text. HTML never travels as HTML: a page the model wrote goes into a
	 * sandboxed frame through `srcdoc`, where it has an opaque origin and cannot reach Hera's
	 * storage. Serving it as a document from this origin would undo that in one header. */
	text: string;
}

export interface MemoryItem {
	/** The filename without its extension, and the identity. Writing it again is a correction,
	 * not a second copy of a fact that changed. */
	key: string;
	text: string;
	/** The one line this screen shows. Deliberately *not* in her prompt — this list is the only
	 * reason it is worth storing, which is why it is worth showing properly. */
	description: string;
	/** What made it worth writing down. Provenance, also not injected. */
	why: string;
	created: string | null;
	scope: 'global' | 'chat';
	chat_id: string;
	source: 'auto' | 'manual';
	enabled: boolean;
	/** What carrying this one costs, counted on the server. The same arithmetic the bar totals,
	 * so a row and the bar above it cannot disagree. */
	tokens: number;
	/** Anything odd about the file, reported rather than raised. */
	problems: string[];
}

/** Prompt and completion tokens, added up. */
export interface Tokens {
	prompt_tokens: number;
	completion_tokens: number;
}

/** Settings → Usage (#111): a bar per day, oldest first and ending today, and three rolling
 * totals. `timezone` is the zone the days were cut in. */
export interface UsageReport {
	days: Array<Tokens & { date: string }>;
	totals: { day: UsageWindow; week: UsageWindow; month: UsageWindow };
	timezone: string;
}

/** One rolling window. Each extra is `null` when nothing in it measured that: no turn
 * reported its cache, none was timed. */
export interface UsageWindow extends Tokens {
	reasoning_tokens: number | null;
	/** Nought to one, over the turns whose endpoint reported its cache. */
	cache_rate: number | null;
	/** Measured by Hera, including the network. */
	tokens_per_second: number | null;
	first_token_ms: number | null;
}

export interface MemoryBudget {
	used: number;
	/** Sent rather than known here: it is a deployment setting, and a bar drawn against a number
	 * the browser guessed would be wrong on exactly the installs that changed it. */
	limit: number;
	count: number;
	disabled: number;
}

export interface AttachmentSummary {
	name: string;
	bytes: number;
	/** `image/png` for a picture, empty for text. The contents never come back, so this is how
	 * a chip knows which kind of thing it is drawing without guessing from the extension. */
	media_type: string;
}

export interface Message {
	id: string;
	role: 'user' | 'assistant';
	content: string;
	sequence: number;
	created_at: string;
	events: AnyEvent[];
	/** Names and sizes only. The contents are not sent back — a chip needs two words, not a
	 * megabyte of source on every chat load. */
	attachments: AttachmentSummary[];
}

export interface ChatDetail {
	chat: Chat;
	messages: Message[];
}

export interface Region {
	id: string;
	title: string;
	purpose: string;
	tier: 'owner_fixed' | 'evolvable';
	text: string;
	generation: number;
	/** The same for everybody here, read from the instance's template (ADR 28). Only an admin
	 * changes it, and the change is everybody's. */
	shared: boolean;
}

/** Whose mind a request means: your own, or the template an admin edits. */
export type MindScope = 'mine' | 'template';

/** Whether this is one you have vouched for. `modified` means listed and changed since. */
export type Trust = 'verified' | 'modified' | 'unknown';

export interface Skill {
	id: string;
	name: string;
	description: string;
	path: string;
	resources: string[];
	problems: string[];
	hits: number;
	enabled: boolean;
	last_used_at: string | null;
	author: string;
	license: string;
	/** An emoji from the frontmatter. Empty is normal — the row draws a monogram instead. */
	icon: string;
	version: string;
	homepage: string;
	digest: string;
	trust: Trust;
}

export interface BrokenSkill {
	id: string;
	path: string;
	reason: string;
}

export interface Server {
	name: string;
	connected: boolean;
	tools: number;
	failure: string | null;
	/** Hera's own server. Shown like the others, not counted as one the person added. */
	builtin: boolean;
	/** False for a block in mcp.json that is switched off: kept, never started. */
	enabled: boolean;
	kind: 'builtin' | 'stdio' | 'http';
}

/** What the add-a-server form edits. A `null` in `env` or `headers` is a secret the server holds
 * and did not send; sending `null` back keeps it. */
export interface ServerEntry {
	kind: 'stdio' | 'http';
	command: string;
	args: string[];
	env: Record<string, string | null>;
	cwd: string;
	url: string;
	headers: Record<string, string | null>;
	enabled: boolean;
}

export interface ServerTool {
	/** `server__tool` — what a permission rule is written against. */
	name: string;
	local_name: string;
	description: string;
	allowed: boolean;
	/** The pattern that turned it off, when something did. */
	rule: string | null;
	/** Whether that rule is on this tool alone, rather than a wider one such as `fs__*`. */
	exact: boolean;
}

export type Decision = 'allow' | 'deny' | 'ask';

export interface Rule {
	pattern: string;
	decision: Decision;
	reason: string;
	profile: string | null;
	/** What a person calls it. Display only: the pattern is the identity. */
	name: string;
	/** `default` ships with Hera, `you` was made on the screen, `card` came from answering
	 * "always" on a confirmation card, `profile` belongs to a profile and is read-only here. */
	source: 'default' | 'you' | 'card' | 'profile';
	/** The tools she has right now that the pattern covers. */
	covers: string[];
}

export interface NewRule {
	pattern: string;
	decision: Decision;
	name?: string;
	reason?: string;
}

export interface RulePatch {
	name?: string;
	decision?: Decision;
	reason?: string;
}

export interface ModelEntry {
	id: string;
	name: string;
	/** Request-body fields this model's server understands and Hera does not — merged into the
	 * body last. Empty for almost everything; GLM-4.7 needs
	 * `chat_template_kwargs.clear_thinking = false` or it reads a multi-turn history as if the
	 * conversation had just started. */
	options: Record<string, unknown>;
	/** How many tokens this model's window holds, for the composer's usage bar. Never probed —
	 * a person fills it in, the same convention as {@link Provider.timeout_s}. `null` draws no
	 * bar at all rather than one pinned at some guessed ceiling. */
	context_length: number | null;
	/** Whether this model is offered tools at all (ADR 19). `false` for a model that writes
	 * what looks like a tool call instead of making one for real — it answers in prose alone
	 * rather than attempting a call it cannot make. */
	tool_calling: boolean;
	/** Whether this model can be shown a picture. Recorded for a later change to read; nothing
	 * refuses an attachment on it yet. */
	accepts_images: boolean;
	/** The `reasoning_effort` values this model accepts, asked of the endpoint. **Empty means
	 * unknown, not "any"** — so a reasoning control is drawn only when this is non-empty. The
	 * values are not a shared vocabulary (OpenRouter carries `minimal`, `none` and `xhigh`, and a
	 * model takes a subset of even that), and a value the server refuses fails the whole request
	 * rather than the setting. */
	reasoning_efforts: string[];
	/** Whether this model reads `chat_template_kwargs.enable_thinking` — the knob most reasoning
	 * models actually have, asked of the endpoint from the chat template it published. A boolean
	 * and not a vocabulary, because that is the shape every model declaring it wants: MiniCPM5 is
	 * *Think* / *No Think*, Qwen and GLM the same. `false` for an endpoint that has not said. */
	thinking_toggle: boolean;
	/** Whether the model wants a thinking **token budget** rather than a named level.
	 *
	 * A third control shape, and the one most easily mistaken for the other two: Anthropic-style
	 * models take `max_tokens` on a thinking block, so offering `low/medium/high` to one
	 * produces a control that does nothing. */
	thinking_budget: boolean;
	/** Which of the three sources answered: a server's name, `declared` for something a person
	 * entered on the settings screen, or `none`. Shown beside the control, because somebody
	 * looking at it is entitled to know whether the endpoint said so or they did. */
	thinking_source: string;
	/** Which control this model wants — `values`, `budget`, `toggle` or `none`. Decided server-side
	 * so the composer and the settings screen cannot disagree about it. */
	thinking_shape: string;
	/** Whether this endpoint's chat template can render a tool declaration — `template`, `none` or
	 * `unknown`. A fact about the template and nothing more: it is *not* a claim that a call will
	 * come back as a call, which needs an engine with a parser for this model's dialect (#145). */
	tool_call_shape: string;
}

/** A known set of {@link ModelEntry.options}, offered on Settings → Models.
 *
 * Served rather than held here, because the server is what validates them — a second copy in
 * TypeScript is a second place they can be wrong, and the one that would be wrong silently. */
export interface ModelPreset {
	id: string;
	label: string;
	hint: string;
	options: Record<string, unknown>;
}

export type ProviderKind =
	| 'openai'
	| 'anthropic'
	| 'google'
	| 'mistral'
	| 'openrouter'
	| 'lmstudio'
	| 'ollama'
	| 'vllm'
	| 'llamacpp'
	| 'generic'
	| 'custom';

export interface Provider {
	name: string;
	kind: ProviderKind;
	base_url: string;
	models: ModelEntry[];
	active_model: string;
	embedding_model: string;
	timeout_s: number;
	connect_timeout_s: number;
	/** Whether a key is stored. The key itself never leaves the machine it was typed on. */
	api_key_set: boolean;
	/** Set only when `kind` is `'custom'` and a logo was uploaded — the media type to expect
	 * from {@link api.logoUrl}, empty when there is none. */
	logo_media_type: string;
}

export interface Providers {
	providers: Provider[];
	active: string;
	presets: ModelPreset[];
}

export interface Probe {
	ok: boolean;
	models: string[];
	error: string;
}

export interface Account {
	id: string;
	name: string;
	email: string;
	role: 'admin' | 'user';
	/** Zero when there is no picture; otherwise a version for {@link api.avatarUrl}, so a
	 * replaced picture is a new address and a cached one cannot outlive it. */
	avatar_version: number;
}

/** Who may make an account here (ADR 27). */
export type Registration = 'open' | 'invite' | 'closed';

/** What the sign-in screen needs before anybody is signed in. */
export interface AuthState {
	user: Account | null;
	setup_required: boolean;
	registration: Registration;
	instance_name: string;
}

/** One browser somebody is signed in on. */
export interface SignedInSession {
	id: string;
	user_agent: string;
	created_at: string;
	last_seen_at: string;
	expires_at: string;
	/** This browser — the one asking. */
	current: boolean;
}

export interface SetupState {
	required: boolean;
	/** False on the machine Hera runs on, which needs no code to prove it could read the log. */
	code_required: boolean;
	/** Conversations an install from before accounts already has, which become the admin's. */
	chats: number;
}

export interface Instance {
	name: string;
	public_url: string;
	registration: Registration;
}

export interface Preferences {
	/** IANA name, or empty for UTC alone. */
	timezone: string;
	/** The sentence she is actually given this turn. Rendered by the server rather than
	 * reconstructed here — the interface formatting a date the same way the prompt does, in a
	 * second place, is two things to keep in step across a daylight-saving change. */
	now: string;
}

export interface Health {
	ok: boolean;
	version: string;
	home: string;
	model: string;
	skills: number;
	servers: Server[];
}

export class ApiError extends Error {
	constructor(
		readonly status: number,
		message: string
	) {
		super(message);
		this.name = 'ApiError';
	}
}

let signedOut: () => void = () => {};

/** What to do when the server says nobody is signed in — the layout points it at `/login`
 * (`$lib/errors`). A hook rather than an import, because the errors module already imports this
 * one for `ApiError`. */
export function whenSignedOut(handler: () => void): void {
	signedOut = handler;
}

/** Hand a 401 from any request to the sign-in screen. The streaming calls below return their
 * response raw, so the chat store calls this for them. */
export function noticeSignedOut(response: Response): void {
	if (response.status === 401) signedOut();
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
	const response = await fetch(`${API}${path}`, {
		...init,
		headers: { 'content-type': 'application/json', ...(init?.headers ?? {}) }
	});
	noticeSignedOut(response);
	if (!response.ok) throw new ApiError(response.status, await detail(response));
	if (response.status === 204) return undefined as T;
	return (await response.json()) as T;
}

async function detail(response: Response): Promise<string> {
	try {
		const body = await response.json();
		// FastAPI puts a string here for a raised HTTPException and a list of field errors for
		// a validation failure. Both are worth showing; neither is worth a special case.
		if (typeof body?.detail === 'string') return body.detail;
		if (body?.detail) return JSON.stringify(body.detail);
	} catch {
		/* not JSON, fall through to the status line */
	}
	return `${response.status} ${response.statusText}`;
}

export const api = {
	health: () => request<Health>('/health'),

	/** Public: who is signed in, if anybody, and what the sign-in screen offers. */
	authState: () => request<AuthState>('/auth/state'),
	signIn: (email: string, password: string) =>
		request<Account>('/auth/sign-in', {
			method: 'POST',
			body: JSON.stringify({ email, password })
		}),
	register: (body: { name: string; email: string; password: string; invite?: string }) =>
		request<Account>('/auth/register', { method: 'POST', body: JSON.stringify(body) }),
	signOut: () => request<void>('/auth/sign-out', { method: 'POST' }),
	sessions: () => request<SignedInSession[]>('/auth/sessions'),
	revokeSession: (id: string) => request<void>(`/auth/sessions/${id}`, { method: 'DELETE' }),
	/** Every browser, this one included. */
	signOutEverywhere: () => request<void>('/auth/sessions', { method: 'DELETE' }),
	/** Signs every *other* browser out. */
	changePassword: (current: string, next: string) =>
		request<void>('/auth/password', {
			method: 'PUT',
			body: JSON.stringify({ current, new: next })
		}),

	setupState: () => request<SetupState>('/setup'),
	/** The wizard's first step: makes the admin and signs this browser in as them. */
	setup: (body: {
		name: string;
		email: string;
		password: string;
		code?: string;
		launch_token?: string;
	}) => request<Account>('/setup', { method: 'POST', body: JSON.stringify(body) }),
	instance: () => request<Instance>('/instance'),
	updateInstance: (patch: Partial<Instance>) =>
		request<Instance>('/instance', { method: 'PATCH', body: JSON.stringify(patch) }),

	profiles: () => request<Profile[]>('/profiles'),
	makeDefaultProfile: (id: string) =>
		request<Profile>(`/profiles/${id}/default`, { method: 'POST' }),

	/** Your own mind, or — for an admin — the template every new person's is cloned from. */
	regions: (scope: MindScope = 'mine') => request<Region[]>(`/mind?scope=${scope}`),
	writeRegion: (id: string, text: string, scope: MindScope = 'mine') =>
		request<Region>(`/mind/${id}?scope=${scope}`, {
			method: 'PUT',
			body: JSON.stringify({ text })
		}),

	projects: () => request<Project[]>('/projects'),
	project: (id: string) => request<Project>(`/projects/${id}`),
	createProject: (name: string) =>
		request<Project>('/projects', { method: 'POST', body: JSON.stringify({ name }) }),
	updateProject: (id: string, patch: ProjectPatch) =>
		request<Project>(`/projects/${id}`, { method: 'PATCH', body: JSON.stringify(patch) }),
	deleteProject: (id: string) => request<void>(`/projects/${id}`, { method: 'DELETE' }),

	chats: () => request<Chat[]>('/chats'),
	createChat: (body: { project_id?: string | null; profile_id?: string | null } = {}) =>
		request<Chat>('/chats', { method: 'POST', body: JSON.stringify(body) }),
	chat: (id: string) => request<ChatDetail>(`/chats/${id}`),
	renameChat: (id: string, title: string) =>
		request<Chat>(`/chats/${id}`, { method: 'PATCH', body: JSON.stringify({ title }) }),
	pinSkills: (id: string, pinned_skills: string[]) =>
		request<Chat>(`/chats/${id}`, { method: 'PATCH', body: JSON.stringify({ pinned_skills }) }),
	/** Move a chat into a project, or out of every project with `null`.
	 *
	 * `project_id` is sent explicitly either way, because the server distinguishes *omitted*
	 * from *null* on this one field — omitting it means "leave it", so a `null` that never
	 * reaches the wire is a move that silently does nothing. */
	moveChat: (id: string, project_id: string | null) =>
		request<Chat>(`/chats/${id}`, { method: 'PATCH', body: JSON.stringify({ project_id }) }),
	deleteChat: (id: string) => request<void>(`/chats/${id}`, { method: 'DELETE' }),

	/** Everything published in one conversation (ADR 13). The file bar, and the count in the
	 * header that says there is something to open. */
	artifacts: (chatId: string) => request<ArtifactSummary[]>(`/chats/${chatId}/artifacts`),
	/** One artifact's *current* content. Fetched by name rather than carried in the event, so a
	 * 40 KB page never bloats a stored message — and so an edit in a later turn changes what an
	 * earlier card draws, which ADR 13 makes deliberate. */
	artifact: (chatId: string, name: string) =>
		request<ArtifactContent>(`/chats/${chatId}/artifacts/${encodeURIComponent(name)}`),
	/** Replace a published file's text with a person's edit. It never makes one: an unknown name
	 * is a 404, so a typo in a document is fixable and a new file is still hers to publish. */
	writeArtifact: (chatId: string, name: string, text: string) =>
		request<ArtifactContent>(`/chats/${chatId}/artifacts/${encodeURIComponent(name)}`, {
			method: 'PUT',
			body: JSON.stringify({ text })
		}),
	/** Tell the server this artifact would not draw, so she hears about it on her next turn.
	 * Only a browser can know: mermaid lays a diagram out by measuring text. */
	reportArtifactProblem: (chatId: string, name: string, message: string) =>
		request<void>(`/chats/${chatId}/artifacts/${encodeURIComponent(name)}/problem`, {
			method: 'PUT',
			body: JSON.stringify({ message })
		}),

	providers: () => request<Providers>('/providers'),
	addProvider: (body: {
		name: string;
		kind?: ProviderKind;
		base_url: string;
		model_id: string;
		model_name?: string;
		model_options?: Record<string, unknown>;
		api_key?: string;
		embedding_model?: string;
		timeout_s?: number;
		connect_timeout_s?: number;
	}) => request<Providers>('/providers', { method: 'POST', body: JSON.stringify(body) }),
	updateProvider: (
		name: string,
		patch: Partial<{
			kind: ProviderKind;
			base_url: string;
			api_key: string;
			embedding_model: string;
			timeout_s: number;
			connect_timeout_s: number;
			logo_data_url: string;
			logo_media_type: string;
		}>
	) => request<Providers>(`/providers/${name}`, { method: 'PATCH', body: JSON.stringify(patch) }),
	activateProvider: (name: string, model?: string) =>
		request<Providers>(`/providers/${name}/activate`, {
			method: 'POST',
			body: JSON.stringify(model ? { model } : {})
		}),
	deleteProvider: (name: string) => request<Providers>(`/providers/${name}`, { method: 'DELETE' }),
	probeProvider: (name: string) => request<Probe>(`/providers/${name}/models`),
	/** Registers a model, or replaces the one already registered under that id — which is how a
	 * model's `options` are edited. They are sent whole: an empty object clears them. */
	addModel: (
		name: string,
		body: {
			id: string;
			name?: string;
			options?: Record<string, unknown>;
			context_length?: number | null;
			tool_calling?: boolean;
			accepts_images?: boolean;
		}
	) =>
		request<Providers>(`/providers/${name}/models`, { method: 'POST', body: JSON.stringify(body) }),
	removeModel: (name: string, modelId: string) =>
		request<Providers>(`/providers/${name}/models?id=${encodeURIComponent(modelId)}`, {
			method: 'DELETE'
		}),
	/** Where a `'custom'`-kind provider's uploaded logo is served from — not fetched through
	 * `request`, since callers hand this straight to an `<img src>`. */
	logoUrl: (name: string) => `${API}/providers/${encodeURIComponent(name)}/logo`,

	skills: () =>
		request<{ skills: Skill[]; broken: BrokenSkill[]; trust_problem: string }>('/skills'),
	/** Creates a skill folder. `content` is a whole SKILL.md and is written as it is. */
	createSkill: (body: { id: string; content: string }) =>
		request<Skill>('/skills', { method: 'POST', body: JSON.stringify(body) }),
	/** Deletes the skill's folder. Not undoable. */
	deleteSkill: (id: string) =>
		request<void>(`/skills/${encodeURIComponent(id)}`, { method: 'DELETE' }),
	/** The skill's SKILL.md verbatim, for the editor. */
	skillSource: (id: string) =>
		request<{ content: string }>(`/skills/${encodeURIComponent(id)}/source`),
	/** Replaces the file. What comes back is what the loader made of it, `problems` included. */
	saveSkillSource: (id: string, content: string) =>
		request<Skill>(`/skills/${encodeURIComponent(id)}/source`, {
			method: 'PUT',
			body: JSON.stringify({ content })
		}),
	/** Off means not routed, not offered to `/slash`, not pinnable. The folder stays. */
	setSkillEnabled: (id: string, enabled: boolean) =>
		request<Skill>(`/skills/${encodeURIComponent(id)}`, {
			method: 'PATCH',
			body: JSON.stringify({ enabled })
		}),

	/** Everything she has written down (ADR 16). Switched-off ones included — the switch is
	 * about what a turn costs, and a list that hid them would leave you unable to switch one
	 * back on. */
	memories: () => request<MemoryItem[]>('/memories'),
	memoryBudget: () => request<MemoryBudget>('/memories/budget'),
	/** What the turns cost, cut into days in `tz` — the browser's own zone, so "today" is the
	 * reader's today. Left empty, the server uses the one set on General, then UTC. */
	usage: (days = 30, tz = '') =>
		request<UsageReport>(`/usage?${new URLSearchParams({ days: String(days), tz })}`),
	/** Edit one, or switch it on or off. A field left out is left alone.
	 *
	 * One call for both because they are one act from the store's side and one row on screen —
	 * this is the door a *person* has. Growing a memory past the ceiling, or switching one back
	 * on when there is no room, comes back a 409 naming what is taking the space. */
	updateMemory: (
		key: string,
		patch: { enabled?: boolean; text?: string; description?: string; why?: string }
	) =>
		request<MemoryItem>(`/memories/${encodeURIComponent(key)}`, {
			method: 'PATCH',
			body: JSON.stringify(patch)
		}),
	/** The only thing anywhere that unlinks a memory. Her own `forget` switches one off and
	 * keeps the file — nothing a person told her is discarded without a person present. */
	deleteMemory: (key: string) =>
		request<void>(`/memories/${encodeURIComponent(key)}`, { method: 'DELETE' }),

	account: () => request<Account>('/account'),
	updateAccount: (patch: { name?: string; email?: string }) =>
		request<Account>('/account', { method: 'PATCH', body: JSON.stringify(patch) }),
	setAvatar: (data_url: string) =>
		request<Account>('/account/avatar', { method: 'PUT', body: JSON.stringify({ data_url }) }),
	removeAvatar: () => request<Account>('/account/avatar', { method: 'DELETE' }),
	/** Where the avatar is served from — an `<img src>`, not fetched through `request`. */
	avatarUrl: (version: number) => `${API}/account/avatar?v=${version}`,

	preferences: () => request<Preferences>('/preferences'),
	setTimezone: (timezone: string) =>
		request<Preferences>('/preferences', {
			method: 'PATCH',
			body: JSON.stringify({ timezone })
		}),

	servers: () => request<Server[]>('/servers'),
	serverTools: (name: string) =>
		request<ServerTool[]>(`/servers/${encodeURIComponent(name)}/tools`),
	/** Turn one tool on or off. Off is a `deny` rule, so it also shows under Permissions. */
	setToolAllowed: (server: string, tool: string, allowed: boolean) =>
		request<ServerTool>(
			`/servers/${encodeURIComponent(server)}/tools/${encodeURIComponent(tool)}`,
			{ method: 'PUT', body: JSON.stringify({ allowed }) }
		),
	serverConfig: (name: string) =>
		request<ServerEntry>(`/servers/${encodeURIComponent(name)}/config`),
	saveServer: (name: string, entry: ServerEntry) =>
		request<Server>(`/servers/${encodeURIComponent(name)}`, {
			method: 'PUT',
			body: JSON.stringify(entry)
		}),
	deleteServer: (name: string) =>
		request<void>(`/servers/${encodeURIComponent(name)}`, { method: 'DELETE' }),
	permissions: () => request<{ fallback: Decision; rules: Rule[] }>('/permissions'),
	createRule: (rule: NewRule) =>
		request<Rule>('/permissions/rules', { method: 'POST', body: JSON.stringify(rule) }),
	/** The pattern is the rule's identity, so it is the path and never part of the patch. */
	updateRule: (pattern: string, patch: RulePatch) =>
		request<Rule>(`/permissions/rules/${encodeURIComponent(pattern)}`, {
			method: 'PATCH',
			body: JSON.stringify(patch)
		}),
	deleteRule: (pattern: string) =>
		request<void>(`/permissions/rules/${encodeURIComponent(pattern)}`, { method: 'DELETE' }),
	setFallback: (fallback: Decision) =>
		request<{ fallback: Decision; rules: Rule[] }>('/permissions', {
			method: 'PATCH',
			body: JSON.stringify({ fallback })
		}),
	/** Your own rules — mostly "always" answered on a card (ADR 28). A layer over the instance's:
	 * each settles an *ask* for you and never loosens a *deny*. */
	myRules: () => request<Rule[]>('/permissions/mine'),
	updateMyRule: (pattern: string, decision: Decision) =>
		request<Rule>(`/permissions/mine/${encodeURIComponent(pattern)}`, {
			method: 'PATCH',
			body: JSON.stringify({ decision })
		}),
	deleteMyRule: (pattern: string) =>
		request<void>(`/permissions/mine/${encodeURIComponent(pattern)}`, { method: 'DELETE' }),
	/** Which of her tools a pattern would cover. Asked as it is typed, so the matcher is the
	 * server's own and the browser holds no second copy of it. */
	ruleMatches: (pattern: string) =>
		request<{ pattern: string; tools: string[] }>(
			`/permissions/matches?pattern=${encodeURIComponent(pattern)}`
		)
};

/** POST a message and get the raw streaming response back. The caller reads it with `frames`. */
export function sendMessage(
	chatId: string,
	text: string,
	attachments: Attachment[] = [],
	signal?: AbortSignal
): Promise<Response> {
	return fetch(`${API}/chats/${chatId}/messages`, {
		method: 'POST',
		headers: { 'content-type': 'application/json' },
		body: JSON.stringify({ text, attachments }),
		signal
	});
}

/** Ask again from a message: new text edits the question, none repeats it. Streams like a
 * send, because from here on it is one. */
export function redoMessage(
	chatId: string,
	messageId: string,
	text?: string,
	signal?: AbortSignal
): Promise<Response> {
	return fetch(`${API}/chats/${chatId}/messages/${messageId}/redo`, {
		method: 'POST',
		headers: { 'content-type': 'application/json' },
		body: JSON.stringify(text === undefined ? {} : { text }),
		signal
	});
}

/** Reply to the questions she asked. Resumes the same assistant message, so it streams too.
 *
 * One call, not a list of calls, which is where this differs from `answerPermission`: several
 * permissions settle with one click because the answer is the same word, and two cards cannot —
 * each wants its own sentences. `answers` is one per question the call held (ADR 26). */
export function answerQuestion(
	chatId: string,
	body: { call_id: string; answers: string[] },
	signal?: AbortSignal
): Promise<Response> {
	return fetch(`${API}/chats/${chatId}/answers`, {
		method: 'POST',
		headers: { 'content-type': 'application/json' },
		body: JSON.stringify(body),
		signal
	});
}

/** Answer a permission card. Resumes the same assistant message, so it streams too. */
export function answerPermission(
	chatId: string,
	body: { call_ids: string[]; allow: boolean; remember?: boolean },
	signal?: AbortSignal
): Promise<Response> {
	return fetch(`${API}/chats/${chatId}/permissions`, {
		method: 'POST',
		headers: { 'content-type': 'application/json' },
		body: JSON.stringify(body),
		signal
	});
}
