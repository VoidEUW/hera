import { describe, expect, it } from 'vitest';
import type { UsageReport } from '$lib/api/client';
import { bars, dayLabel, isEmpty } from './usage';

const zero = { prompt_tokens: 0, completion_tokens: 0 };

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
			isEmpty(report([['2026-10-26', 0, 0]], { prompt_tokens: 9, completion_tokens: 1 }))
		).toBe(false);
	});
});
