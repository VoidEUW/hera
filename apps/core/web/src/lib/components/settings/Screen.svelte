<script lang="ts">
	/**
	 * The top of every settings screen: what this is, in a heading and one line.
	 *
	 * The modal's own header is only a close button, so the title lives here, in the content,
	 * where it says what the screen in front of you is rather than repeating what the modal is.
	 * Kept compact — it is the first thing every screen draws and must not push the content
	 * down the way the old display heading did.
	 */
	interface Props {
		title: string;
		blurb?: string;
		children?: import('svelte').Snippet;
	}

	let { title, blurb = '', children }: Props = $props();
</script>

<header>
	<h2>{title}</h2>
	{#if blurb}<p class="caption">{blurb}</p>{/if}
</header>
{#if children}
	{@render children()}
{/if}

<style>
	header {
		margin-bottom: 10px;
		padding-bottom: 12px;
		border-bottom: 1px solid var(--line);
	}

	h2 {
		margin: 0;
		font-family: var(--font-ui);
		font-size: 17px;
		font-weight: 600;
	}

	p {
		margin: 3px 0 0;
	}
</style>
