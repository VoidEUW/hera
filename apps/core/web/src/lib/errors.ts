/**
 * What went wrong, said the way the error page says it (`ui/ErrorPage.svelte`).
 *
 * A screen that failed to load used to print whatever the request threw as one line —
 * `500 Internal Server Error` — which is the server's words for the server's log, not a person's.
 * This reads the failure once and hands back the kind (which bends the mark), a status line a
 * person can search for, a title and a sentence about what to do, and the server's own words
 * kept behind a disclosure for whoever has to fix it.
 */
import { ApiError } from '$lib/api/client';
import { t } from '$lib/i18n';

export interface Failure {
	kind: 'offline' | 'server' | 'not-found';
	code: string;
	title: string;
	body: string;
	detail: { label: string; text: string };
}

/** `what` names the thing that failed to load — "usage", "her mind regions". */
export function failure(cause: unknown, what: string): Failure {
	const said = cause instanceof Error ? cause.message : String(cause);
	const detail = (text: string) => ({ label: t.loadFailed.detail, text });

	if (!(cause instanceof ApiError)) {
		// `fetch` itself failed: nothing answered at all.
		return {
			kind: 'offline',
			code: t.errorPage.offline,
			title: t.loadFailed.offlineTitle(what),
			body: t.loadFailed.offlineBody,
			detail: detail(said)
		};
	}
	const text = `${cause.status} · ${said}`;
	if (cause.status === 404) {
		return {
			kind: 'not-found',
			code: `404 · ${t.loadFailed.notFound}`,
			title: t.loadFailed.notFoundTitle(what),
			body: t.loadFailed.notFoundBody,
			detail: detail(text)
		};
	}
	return {
		kind: 'server',
		code: `${cause.status} · ${cause.status >= 500 ? t.errorPage.server : t.loadFailed.refused}`,
		title: t.loadFailed.serverTitle(what),
		body: cause.status >= 500 ? t.loadFailed.serverBody : t.loadFailed.refusedBody,
		detail: detail(text)
	};
}
