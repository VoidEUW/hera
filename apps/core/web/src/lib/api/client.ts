/**
 * The API, typed.
 *
 * One origin, no CORS, no base URL to configure: the interface is served by the application it
 * talks to (ADR 6). Every function here is a thin wrapper whose only job is to turn a non-2xx
 * into an error with the server's own `detail` in it — a fetch that silently returns an error
 * body as if it were data is the bug this file exists to prevent.
 */

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
	archived: boolean;
}

export interface Chat {
	id: string;
	title: string;
	project_id: string | null;
	profile_id: string | null;
	pinned: boolean;
	created_at: string;
	last_message_at: string | null;
}

export interface AttachmentSummary {
	name: string;
	bytes: number;
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
}

export interface Skill {
	id: string;
	name: string;
	description: string;
	path: string;
	resources: string[];
	problems: string[];
	hits: number;
	last_used_at: string | null;
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
}

export interface Rule {
	pattern: string;
	decision: 'allow' | 'deny' | 'ask';
	reason: string;
	profile: string | null;
}

export interface Provider {
	name: string;
	base_url: string;
	model: string;
	embedding_model: string;
	timeout_s: number;
	connect_timeout_s: number;
	/** Whether a key is stored. The key itself never leaves the machine it was typed on. */
	api_key_set: boolean;
}

export interface Providers {
	providers: Provider[];
	active: string;
}

export interface Probe {
	ok: boolean;
	models: string[];
	error: string;
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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
	const response = await fetch(`${API}${path}`, {
		...init,
		headers: { 'content-type': 'application/json', ...(init?.headers ?? {}) }
	});
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

	profiles: () => request<Profile[]>('/profiles'),
	makeDefaultProfile: (id: string) =>
		request<Profile>(`/profiles/${id}/default`, { method: 'POST' }),

	regions: () => request<Region[]>('/mind'),
	writeRegion: (id: string, text: string) =>
		request<Region>(`/mind/${id}`, { method: 'PUT', body: JSON.stringify({ text }) }),

	projects: () => request<Project[]>('/projects'),
	createProject: (name: string) =>
		request<Project>('/projects', { method: 'POST', body: JSON.stringify({ name }) }),
	updateProject: (id: string, patch: Partial<Project>) =>
		request<Project>(`/projects/${id}`, { method: 'PATCH', body: JSON.stringify(patch) }),
	deleteProject: (id: string) => request<void>(`/projects/${id}`, { method: 'DELETE' }),

	chats: () => request<Chat[]>('/chats'),
	createChat: (body: { project_id?: string | null; profile_id?: string | null } = {}) =>
		request<Chat>('/chats', { method: 'POST', body: JSON.stringify(body) }),
	chat: (id: string) => request<ChatDetail>(`/chats/${id}`),
	deleteChat: (id: string) => request<void>(`/chats/${id}`, { method: 'DELETE' }),

	providers: () => request<Providers>('/providers'),
	addProvider: (body: Partial<Provider> & { name: string; api_key?: string }) =>
		request<Providers>('/providers', { method: 'POST', body: JSON.stringify(body) }),
	updateProvider: (name: string, patch: Partial<Provider> & { api_key?: string }) =>
		request<Providers>(`/providers/${name}`, { method: 'PATCH', body: JSON.stringify(patch) }),
	activateProvider: (name: string) =>
		request<Providers>(`/providers/${name}/activate`, { method: 'POST' }),
	deleteProvider: (name: string) => request<Providers>(`/providers/${name}`, { method: 'DELETE' }),
	probeProvider: (name: string) => request<Probe>(`/providers/${name}/models`),

	skills: () => request<{ skills: Skill[]; broken: BrokenSkill[] }>('/skills'),
	servers: () => request<Server[]>('/servers'),
	permissions: () => request<{ fallback: string; rules: Rule[] }>('/permissions')
};

/** POST a message and get the raw streaming response back. The caller reads it with `frames`. */
export function sendMessage(
	chatId: string,
	text: string,
	attachments: Array<{ name: string; text: string; bytes: number }> = [],
	signal?: AbortSignal
): Promise<Response> {
	return fetch(`${API}/chats/${chatId}/messages`, {
		method: 'POST',
		headers: { 'content-type': 'application/json' },
		body: JSON.stringify({ text, attachments }),
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
