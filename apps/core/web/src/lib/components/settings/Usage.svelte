<script lang="ts">
	/**
	 * How many tokens her answers took, day by day (#111).
	 *
	 * Read from the server's ledger (ADR 25), which keeps what a turn cost after the chat it was
	 * in is deleted — so this is what was spent, not what happens to be left. The days are cut
	 * in this browser's time zone, because "yesterday" is a fact about where the reader is.
	 *
	 * The chart comes first and answers *is it a lot, and is it growing*; the three totals under
	 * it answer *how much*. Read and written are drawn apart because they are different costs:
	 * read is mostly the conversation and her mind sent again each turn, written is her answer.
	 */
	import { api, type UsageReport, type UsageWindow } from '$lib/api/client';
	import BarChart from '$lib/components/ui/BarChart.svelte';
	import { t } from '$lib/i18n';
	import { Placeholder } from '$lib/loading.svelte';
	import { bars, browserZone, isEmpty, rate, seconds, speed } from '$lib/usage';
	import LoadFailed from './LoadFailed.svelte';
	import Rows from './Rows.svelte';

	const DAYS = 30;

	let report = $state<UsageReport | null>(null);
	/** Why the report could not be read, if it could not. Kept as thrown, for `LoadFailed`. */
	let failed = $state<unknown>(null);

	/** Set where the load begins and ends, as on Memory: a fetch from this machine can finish
	 * before effects next flush, and an effect over a flag would never draw the placeholder. */
	const settling = new Placeholder(true);
	$effect(() => () => settling.stop());

	const zone = browserZone();

	$effect(() => {
		void load();
	});

	async function load() {
		try {
			report = await api.usage(DAYS, zone);
			failed = null;
		} catch (cause) {
			failed = cause;
		} finally {
			settling.set(false);
		}
	}

	const drawn = $derived(report ? bars(report) : []);
	const totals = $derived(
		report
			? ([
					[t.usage.day, report.totals.day],
					[t.usage.week, report.totals.week],
					[t.usage.month, report.totals.month]
				] as Array<[string, UsageWindow]>)
			: []
	);
</script>

{#if settling.shown}
	<Rows label={t.usage.loading} />
{:else if failed !== null}
	<LoadFailed cause={failed} what={t.loadFailed.what.usage} onretry={load} />
{:else if report}
	<section class="usage">
		{#if isEmpty(report)}
			<p class="empty">{t.usage.none}</p>
		{:else}
			<BarChart
				bars={drawn}
				series={[
					{ label: t.usage.prompt, tone: 'quiet', hint: t.usage.promptLong },
					{ label: t.usage.completion, tone: 'live', hint: t.usage.completionLong }
				]}
				label={t.usage.chart(DAYS)}
				describe={(bar) => t.usage.readout(bar.label, bar.values[0], bar.values[1])}
				ends={[drawn[0]?.label ?? '', drawn[drawn.length - 1]?.label ?? '']}
			/>
		{/if}

		<dl class="totals">
			{#each totals as [label, tokens] (label)}
				<div class="total">
					<dt>{label}</dt>
					<dd>
						<strong>{t.usage.tokens(tokens.prompt_tokens + tokens.completion_tokens)}</strong>
						<span>{t.usage.split(tokens.prompt_tokens, tokens.completion_tokens)}</span>
						{#if tokens.reasoning_tokens}
							<span>{t.usage.reasoning(tokens.reasoning_tokens)}</span>
						{/if}
						<!-- Each only when something measured it: a nought here would be a claim
						     nobody made. -->
						{#if tokens.cache_rate !== null}
							<span class="extra">{t.usage.cache(rate(tokens.cache_rate))}</span>
						{/if}
						{#if tokens.tokens_per_second !== null && tokens.first_token_ms !== null}
							<span class="extra">
								{t.usage.pace(speed(tokens.tokens_per_second), seconds(tokens.first_token_ms))}
							</span>
						{/if}
					</dd>
				</div>
			{/each}
		</dl>

		<p class="note">
			{t.usage.note}
			{#if report.timezone !== zone}{t.usage.zone(report.timezone)}.{/if}
		</p>
	</section>
{/if}

<style>
	.usage {
		display: flex;
		flex-direction: column;
		gap: 18px;
	}

	.totals {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 10px;
		margin: 0;
	}

	.total {
		padding: 12px 14px;
		border: var(--border-width) solid var(--line);
		border-radius: var(--radius);
		background: var(--surface);
	}

	dt {
		font-size: 12px;
		color: var(--text-faint);
	}

	dd {
		display: flex;
		flex-direction: column;
		gap: 2px;
		margin: 4px 0 0;
		font-variant-numeric: tabular-nums;
	}

	strong {
		font-size: 17px;
		font-weight: 500;
		color: var(--text);
	}

	dd span {
		font-size: 12px;
		color: var(--text-muted);
	}

	dd .extra {
		color: var(--text-faint);
	}

	.note,
	.empty {
		margin: 0;
		max-width: var(--measure);
		font-size: 12.5px;
		color: var(--text-faint);
	}

	.empty {
		font-size: 13.5px;
		color: var(--text-muted);
	}

	@media (max-width: 600px) {
		.totals {
			grid-template-columns: 1fr;
		}
	}
</style>
