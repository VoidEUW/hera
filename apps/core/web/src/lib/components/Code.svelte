<script lang="ts">
	/** Two angle brackets and a slash: the source of the thing, rather than the thing. */
	interface Props {
		size?: number;
	}

	let { size = 13 }: Props = $props();
</script>

<svg
	class="code"
	width={size}
	height={size}
	viewBox="0 0 16 16"
	fill="none"
	stroke="currentColor"
	stroke-width="1.4"
	stroke-linecap="round"
	stroke-linejoin="round"
	aria-hidden="true"
>
	<path d="M5.4 4.6 2 8l3.4 3.4" />
	<path d="M10.6 4.6 14 8l-3.4 3.4" />
	<path d="M9 3.4 7 12.6" />
</svg>

<style>
	.code {
		display: block;
	}
</style>
