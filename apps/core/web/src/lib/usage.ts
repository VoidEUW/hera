/**
 * Settings → Usage (#111): turning the server's report into what the chart draws.
 *
 * Nothing here adds anything up. The days and the totals are arithmetic the server already did
 * over its ledger, and doing any of it a second time in the browser is how a bar and the total
 * under it come to disagree.
 */
import type { UsageReport } from '$lib/api/client';
import type { Bar } from '$lib/components/ui/BarChart.svelte';

/** The zone this browser is in, so "today" on the chart is the reader's today. */
export function browserZone(): string {
	try {
		return Intl.DateTimeFormat().resolvedOptions().timeZone ?? '';
	} catch {
		return '';
	}
}

/** `2026-10-26` as a person reads it: `Mon 26 Oct`.
 *
 * Read as midnight UTC and written out in UTC, because it is a calendar date and not a moment
 * — formatting it in the browser's zone would move it a day west of Greenwich. */
export function dayLabel(date: string, locale?: string): string {
	return new Intl.DateTimeFormat(locale, {
		weekday: 'short',
		day: 'numeric',
		month: 'short',
		timeZone: 'UTC'
	}).format(new Date(`${date}T00:00:00Z`));
}

/** One bar per day, prompt below completion. */
export function bars(report: UsageReport, locale?: string): Bar[] {
	return report.days.map((day) => ({
		label: dayLabel(day.date, locale),
		values: [day.prompt_tokens, day.completion_tokens]
	}));
}

/** Nothing has been counted in the whole window — a fresh install, or an endpoint that has
 * never reported usage. */
export function isEmpty(report: UsageReport): boolean {
	const { prompt_tokens, completion_tokens } = report.totals.month;
	return (
		prompt_tokens + completion_tokens === 0 &&
		report.days.every((day) => day.prompt_tokens + day.completion_tokens === 0)
	);
}
