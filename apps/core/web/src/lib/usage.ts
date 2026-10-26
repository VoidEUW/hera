/**
 * Settings → Usage (#111): turning the server's report into what the chart draws.
 *
 * Nothing here adds anything up. The days and the totals are arithmetic the server already did
 * over its ledger, and doing any of it a second time in the browser is how a bar and the total
 * under it come to disagree.
 */
import type { UsageReport } from '$lib/api/client';
import type { TurnClosed, TurnTiming } from '$lib/api/events';
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

/** How full the window is after a turn: its last round's prompt and completion.
 *
 * A turn stored before that was recorded only has the sum of its rounds, which reads high on a
 * turn that used tools — still the best figure there is for it, so it is used rather than none. */
export function contextOf(closed: TurnClosed | null | undefined): number | null {
	if (!closed) return null;
	if (closed.context_tokens != null) return closed.context_tokens;
	if (!closed.usage) return null;
	return closed.usage.prompt_tokens + closed.usage.completion_tokens;
}

/** Tokens per second while writing, or `null` when the turn was not both timed and counted. */
export function speedOf(timing: TurnTiming | null | undefined): number | null {
	if (!timing || timing.generating_ms <= 0 || timing.timed_completion_tokens <= 0) return null;
	return timing.timed_completion_tokens / (timing.generating_ms / 1000);
}

/** `48 tok/s` — whole numbers, because a tenth of a token a second is noise. */
export function speed(perSecond: number): string {
	return `${Math.round(perSecond).toLocaleString()} tok/s`;
}

/** `850 ms` below a second, `1.2 s` above it. */
export function seconds(ms: number): string {
	return ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`;
}

/** `72%` — a share from nought to one. */
export function rate(share: number): string {
	return `${Math.round(share * 100)}%`;
}
