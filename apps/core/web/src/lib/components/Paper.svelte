<script lang="ts">
	/**
	 * A sheet with writing on it — what an artifact is: something she wrote and kept.
	 *
	 * Same hand and weight as `Tray` and `Copy`, and it takes its colour from where it sits.
	 * `muted` is the card's way of saying *this one is in the flow of the answer*.
	 */
	interface Props {
		size?: number;
		muted?: boolean;
	}

	let { size = 14, muted = false }: Props = $props();
</script>

<svg
	class="paper"
	class:muted
	width={size}
	height={size}
	viewBox="0 0 16 16"
	fill="none"
	stroke="currentColor"
	stroke-width="1.3"
	stroke-linecap="round"
	stroke-linejoin="round"
	aria-hidden="true"
>
	<path d="M4 1.8h5.4L12.6 5v8.4a.8.8 0 0 1-.8.8H4a.8.8 0 0 1-.8-.8V2.6A.8.8 0 0 1 4 1.8Z" />
	<path d="M9.2 1.8v3.4h3.4" />
	<path d="M5.4 8h5.2M5.4 10.2h5.2M5.4 12.2h3" />
</svg>

<style>
	.paper {
		display: block;
		color: var(--brass);
	}

	.paper.muted {
		color: var(--text-faint);
	}
</style>
