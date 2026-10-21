<script lang="ts">
	/**
	 * Asking before something is lost (the theme's open dialog, small): a title, one sentence, and
	 * two buttons — the safe one first in reading order, the destructive one last and `danger`.
	 *
	 * A `Modal`, so it is a dialog to a keyboard like every other: focus moves in, Tab stays in,
	 * Escape answers *no*. It never asks twice and never decides what *yes* does; the caller owns
	 * that, because only it knows what is being thrown away.
	 */
	import Button from './Button.svelte';
	import Modal from './Modal.svelte';

	interface Props {
		title: string;
		/** The one sentence under the title: what goes if the answer is yes. */
		body: string;
		/** What the destructive button says — a verb, not "OK". */
		confirm: string;
		cancel: string;
		onconfirm: () => void;
		oncancel: () => void;
	}

	let { title, body, confirm, cancel, onconfirm, oncancel }: Props = $props();
</script>

<Modal label={title} {title} caption={body} width="min(420px, 92vw)" onclose={oncancel}>
	{#snippet footer()}
		<Button variant="ghost" onclick={oncancel}>{cancel}</Button>
		<Button variant="danger" onclick={onconfirm}>{confirm}</Button>
	{/snippet}
</Modal>
