import { describe, expect, it } from 'vitest';
import { ApiError } from '$lib/api/client';
import { failure } from './errors';

describe('failure', () => {
	it('names a server fault by its status, and keeps what the server said', () => {
		const shown = failure(new ApiError(500, 'Internal Server Error'), 'usage');
		expect(shown.kind).toBe('server');
		expect(shown.code).toBe('500 · Server error');
		expect(shown.title).toBe('Could not load usage');
		expect(shown.detail.text).toBe('500 · Internal Server Error');
	});

	it('says a refusal is a refusal, not a crash', () => {
		const shown = failure(new ApiError(422, "'Mars/Olympus' is not a time zone"), 'usage');
		expect(shown.kind).toBe('server');
		expect(shown.code).toBe('422 · Refused');
		expect(shown.body).toMatch(/refused/);
	});

	it('reads a missing route as an interface newer than its server', () => {
		const shown = failure(new ApiError(404, 'Not Found'), 'usage');
		expect(shown.kind).toBe('not-found');
		expect(shown.body).toMatch(/Restart hera serve/);
	});

	it('reads a fetch that never got an answer as the server being gone', () => {
		const shown = failure(new TypeError('Failed to fetch'), 'usage');
		expect(shown.kind).toBe('offline');
		expect(shown.detail.text).toBe('Failed to fetch');
	});

	it('copes with something thrown that is not an error at all', () => {
		expect(failure('nope', 'usage').detail.text).toBe('nope');
	});
});
