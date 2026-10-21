<script lang="ts">
	/**
	 * Hera's own find, in the top bar of a chat (#112, `⌘F`): a field, how many matches and which
	 * one, and previous / next. Matches are painted with the CSS Custom Highlight API over the
	 * transcript's own text, so nothing in it is rewrapped or re-rendered — and a match is a run
	 * of text inside one element, which is what a person looks for.
	 *
	 * It looks again when the transcript changes, because the thing being searched is often still
	 * arriving. Enter goes to the next match, Shift+Enter to the one before, and Escape clears the
	 * field and then closes — the field's own Escape first, like every field here.
	 */
	import { tick, untrack } from 'svelte';
	import { t } from '$lib/i18n';
	import CloseButton from './ui/CloseButton.svelte';
	import IconButton from './ui/IconButton.svelte';
	import SearchBar from './ui/SearchBar.svelte';

	interface Props {
		/** The element whose text is searched: the scrolling transcript. */
		root: HTMLElement | null;
		onclose: () => void;
	}

	let { root, onclose }: Props = $props();

	let query = $state('');
	let field = $state<HTMLInputElement | null>(null);
	let ranges = $state.raw<Range[]>([]);
	let at = $state(0);
	/** Bumped when the transcript changes, to look again. */
	let version = $state(0);

	$effect(() => {
		field?.focus();
	});

	/** Every occurrence of `needle` in a visible text node of `within`. */
	function search(within: HTMLElement, needle: string): Range[] {
		const found: Range[] = [];
		if (!needle) return found;
		const lower = needle.toLowerCase();
		const walker = document.createTreeWalker(within, NodeFilter.SHOW_TEXT);
		for (let node = walker.nextNode(); node; node = walker.nextNode()) {
			const parent = node.parentElement;
			if (!parent || parent.closest('script, style, [hidden], [inert], [aria-hidden="true"]'))
				continue;
			if (parent.offsetParent === null && getComputedStyle(parent).position !== 'fixed') continue;
			const text = (node.textContent ?? '').toLowerCase();
			for (let from = text.indexOf(lower); from !== -1; from = text.indexOf(lower, from + 1)) {
				const range = new Range();
				range.setStart(node, from);
				range.setEnd(node, from + needle.length);
				found.push(range);
			}
		}
		return found;
	}

	$effect(() => {
		void version;
		const needle = query;
		const within = root;
		if (!within) return;
		const found = search(within, needle);
		ranges = found;
		untrack(() => {
			if (at >= found.length) at = 0;
		});
	});

	// A new question starts at the first match.
	$effect(() => {
		void query;
		untrack(() => (at = 0));
	});

	// The transcript grows while she answers; look again a moment after it settles.
	$effect(() => {
		if (!root) return;
		let timer: ReturnType<typeof setTimeout> | undefined;
		const watch = new MutationObserver(() => {
			clearTimeout(timer);
			timer = setTimeout(() => (version += 1), 150);
		});
		watch.observe(root, { childList: true, characterData: true, subtree: true });
		return () => {
			clearTimeout(timer);
			watch.disconnect();
		};
	});

	// Paint: every match softly, the current one firmly.
	$effect(() => {
		if (!('highlights' in CSS)) return;
		CSS.highlights.set('find', new Highlight(...ranges));
		const current = ranges[at];
		if (current) CSS.highlights.set('find-current', new Highlight(current));
		else CSS.highlights.delete('find-current');
		return () => {
			CSS.highlights.delete('find');
			CSS.highlights.delete('find-current');
		};
	});

	/** Bring the current match into view, without moving anything that already shows it. */
	async function show() {
		await tick();
		ranges[at]?.startContainer.parentElement?.scrollIntoView({ block: 'center' });
	}

	function go(by: 1 | -1) {
		if (!ranges.length) return;
		at = (at + by + ranges.length) % ranges.length;
		void show();
	}

	// The first match is shown as it is found.
	$effect(() => {
		if (ranges.length && at === 0) void show();
	});

	function onkeydown(event: KeyboardEvent) {
		if (event.key === 'Enter') {
			event.preventDefault();
			go(event.shiftKey ? -1 : 1);
		} else if (event.key === 'Escape' && !event.defaultPrevented) {
			event.preventDefault();
			event.stopPropagation();
			onclose();
		}
	}

	const status = $derived(
		!query ? '' : ranges.length ? t.find.count(at + 1, ranges.length) : t.find.none
	);
</script>

<div class="find" role="search" aria-label={t.find.label}>
	<div class="field">
		<SearchBar
			bind:ref={field}
			value={query}
			placeholder={t.find.placeholder}
			onchange={(value) => (query = value)}
			{onkeydown}
		/>
	</div>
	<span class="count" aria-live="polite">{status}</span>
	<IconButton
		icon="chevU"
		label={t.find.previous}
		disabled={!ranges.length}
		onclick={() => go(-1)}
	/>
	<IconButton icon="chevD" label={t.find.next} disabled={!ranges.length} onclick={() => go(1)} />
	<CloseButton size="sm" label={t.find.close} onclick={onclose} />
</div>

<style>
	.find {
		display: flex;
		flex: none;
		align-items: center;
		gap: 6px;
		padding: 0 12px 8px 24px;
	}

	.field {
		flex: 0 1 320px;
		min-width: 0;
	}

	.count {
		min-width: 64px;
		color: var(--text-faint);
		font-family: var(--font-mono);
		font-size: 11.5px;
		white-space: nowrap;
	}
</style>
