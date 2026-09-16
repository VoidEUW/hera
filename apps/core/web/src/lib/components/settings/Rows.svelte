<script lang="ts">
	/**
	 * What a settings screen looks like before it has answered: a few rows, the shape of the
	 * rows it is about to have.
	 *
	 * One placeholder for all six screens rather than a bespoke one each. What Models, Skills,
	 * Memory, Servers, Permissions and Mind actually draw could hardly be less alike, but all of
	 * them draw it as a list of rows with a heading and a line under it, and a panel that holds
	 * a different shape for every tab is a panel that looks like it is loading six different
	 * things. The point of this is that switching tabs is calm.
	 */
	import Skeleton from '../Skeleton.svelte';

	interface Props {
		/** How many rows. Four is about a screenful at the modal's height. */
		rows?: number;
		/** What is loading. One region announces it; the bars inside are decoration. */
		label: string;
	}

	let { rows = 4, label }: Props = $props();

	/** Cycled rather than fixed, so the block reads as a list of different things rather than as
	 * the same row printed four times. */
	const HEADS = [34, 27, 41, 30];
	const LINES = [62, 78, 55, 70];
</script>

<div class="rows" role="status" aria-busy="true" aria-label={label}>
	{#each { length: rows }, index (index)}
		<div class="row">
			<Skeleton
				rows={2}
				height={13}
				gap={7}
				widths={[HEADS[index % HEADS.length], LINES[index % LINES.length]]}
			/>
		</div>
	{/each}
</div>

<style>
	/* `.row` in `Settings.svelte`, which is what every one of these screens lays its list out
	   as: 14px of air above and below, a hairline between. Copied rather than shared because
	   the two files cannot see each other's scoped styles, and the four numbers are the whole
	   of it. */
	.row {
		padding: 14px 0;
		border-bottom: 1px solid var(--line);
		/* The sheet is `--surface-raised`, so the bar's own default is the colour it is lying on
		   and cannot be seen at all. Mixed toward the text rather than reached for by name:
		   `--line` is lighter than the sheet in the dark theme and darker than it in the light
		   one, and in the light one barely by enough — a fixed step *towards the reading colour*
		   is a step in the visible direction whichever way round the room is. */
		--skeleton-bar: color-mix(in oklab, var(--text-faint) 35%, var(--surface-raised));
		--skeleton-sheen: color-mix(in oklab, var(--text-faint) 58%, var(--surface-raised));
	}
</style>
