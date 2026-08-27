<script lang="ts">
	/**
	 * A run of her prose, as Markdown and TeX.
	 *
	 * Everything visual lives in `app.css` under `.prose`, not here: the rendered HTML comes out
	 * of `{@html}` and Svelte's scoped styles never reach it, so a rule written here would
	 * silently apply to nothing.
	 *
	 * The copy button on a code block is wired the same way round. The button is markup from
	 * `$lib/markdown`, and the click is caught **once on the container** by an action — Svelte
	 * cannot bind a handler to something it did not render, and one listener that reads the code
	 * off the DOM beats an attribute carrying a second copy of every program she writes.
	 */
	import { t } from '$lib/i18n';
	import { render } from '$lib/markdown';

	interface Props {
		text: string;
	}

	let { text }: Props = $props();

	const html = $derived(render(text));

	function copyable(node: HTMLElement) {
		async function onclick(event: MouseEvent) {
			const button = (event.target as HTMLElement | null)?.closest('button.copy');
			if (!(button instanceof HTMLElement)) return;
			const code = button.closest('figure')?.querySelector('code')?.textContent ?? '';
			try {
				await navigator.clipboard.writeText(code);
			} catch {
				return; // a browser that refuses the clipboard is not worth an alarm
			}
			// Written straight into the DOM: this element is not Svelte's to re-render, and the
			// label going back to "Copy" on the next delta is the correct amount of memory for
			// a confirmation to have.
			button.textContent = t.message.copied;
			setTimeout(() => (button.textContent = t.message.copy), 1400);
		}

		node.addEventListener('click', onclick);
		return { destroy: () => node.removeEventListener('click', onclick) };
	}
</script>

<div class="prose" use:copyable>
	<!-- eslint-disable-next-line svelte/no-at-html-tags -- sanitised in $lib/markdown -->
	{@html html}
</div>
