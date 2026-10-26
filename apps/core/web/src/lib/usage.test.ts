import { describe, expect, it } from 'vitest';
import type { UsageReport } from '$lib/api/client';
import { bars, contextOf, dayLabel, isEmpty, rate, seconds, speed, speedOf } from './usage';

const zero = {
	prompt_tokens: 0,
	completion_tokens: 0,
	reasoning_tokens: null,
	cache_rate: null,
	tokens_per_second: null,
	first_token_ms: null
};

function report(days: Array<[string, number, number]>, month = zero): UsageReport {
	return {
		days: days.map(([date, prompt_tokens, completion_tokens]) => ({
			date,
			prompt_tokens,
			completion_tokens
		})),
		totals: { day: zero, week: zero, month },
		timezone: 'UTC'
	};
}

describe('dayLabel', () => {
	it('writes the calendar date it was given, wherever the browser is', () => {
		// A date, not a moment: read in a zone west of Greenwich it would otherwise be the 25th.
		expect(dayLabel('2026-10-26', 'en-GB')).toBe('Mon 26 Oct');
	});
});

describe('bars', () => {
	it('is one bar per day, prompt first, in the order the server sent', () => {
		const drawn = bars(
			report([
				['2026-10-25', 100, 10],
				['2026-10-26', 300, 20]
			]),
			'en-GB'
		);
		expect(drawn).toEqual([
			{ label: 'Sun 25 Oct', values: [100, 10] },
			{ label: 'Mon 26 Oct', values: [300, 20] }
		]);
	});
});

describe('isEmpty', () => {
	it('is empty when nothing was counted', () => {
		expect(isEmpty(report([['2026-10-26', 0, 0]]))).toBe(true);
	});

	it('is not empty when a day has tokens', () => {
		expect(isEmpty(report([['2026-10-26', 5, 0]]))).toBe(false);
	});

	it('is not empty when only the month has tokens, beyond a short chart', () => {
		expect(
			isEmpty(report([['2026-10-26', 0, 0]], { ...zero, prompt_tokens: 9, completion_tokens: 1 }))
		).toBe(false);
	});
});

describe('contextOf', () => {
	const close = (over: Record<string, unknown>) =>
		({
			type: 'turn_closed',
			reason: 'completed',
			usage: null,
			iterations: 1,
			error: '',
			...over
		}) as never;

	it('is the recorded last round', () => {
		expect(contextOf(close({ context_tokens: 900 }))).toBe(900);
	});

	it('falls back to prompt plus completion for a turn stored before that was recorded', () => {
		expect(
			contextOf(close({ usage: { prompt_tokens: 100, completion_tokens: 5, total_tokens: 0 } }))
		).toBe(105);
	});

	it('is null with nothing reported', () => {
		expect(contextOf(close({}))).toBeNull();
		expect(contextOf(null)).toBeNull();
	});
});

describe('speedOf', () => {
	it('is timed tokens over the time spent writing', () => {
		expect(
			speedOf({
				first_token_ms: 300,
				waiting_ms: 300,
				generating_ms: 2000,
				timed_completion_tokens: 96
			})
		).toBe(48);
	});

	it('is null when nothing was both timed and counted', () => {
		expect(
			speedOf({
				first_token_ms: 300,
				waiting_ms: 300,
				generating_ms: 0,
				timed_completion_tokens: 0
			})
		).toBeNull();
		expect(speedOf(null)).toBeNull();
	});
});

describe('formatting', () => {
	it('says a speed in whole tokens', () => {
		expect(speed(47.6)).toBe('48 tok/s');
	});

	it('says milliseconds below a second and seconds above', () => {
		expect(seconds(850)).toBe('850 ms');
		expect(seconds(1234)).toBe('1.2 s');
	});

	it('says a share as a percentage', () => {
		expect(rate(0.724)).toBe('72%');
	});
});
