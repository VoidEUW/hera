<script lang="ts">
	/**
	 * What you can do with the conversation as a whole, from its own top bar: export it, share it
	 * (greyed — a feature you can see coming is a promise, #101), delete it behind the same
	 * two-step the rail's menu uses. The rail's row menu does these for *any* chat; this one is for
	 * the chat you are in, which is why a key can be bound to each (#112): every chord mirrors a
	 * control that is on screen.
	 */
	import { API } from '$lib/api/client';
	import { keys } from '$lib/keys';
	import { t } from '$lib/i18n';
	import IconButton from './ui/IconButton.svelte';
	import Menu from './ui/Menu.svelte';
	import MenuItem from './ui/MenuItem.svelte';
	import MenuNote from './ui/MenuNote.svelte';
	import MenuSeparator from './ui/MenuSeparator.svelte';

	interface Props {
		chatId: string;
		/** How many files she published here, said in the delete question because they go too. */
		published?: number;
		ondelete: () => void;
	}

	let { chatId, published = 0, ondelete }: Props = $props();

	let open = $state(false);
	let confirming = $state(false);
	let anchor = $state<HTMLElement | null>(null);

	// The chords for what is in this menu: the menu is the control they mirror (#112).
	$effect(() => {
		const off = [
			keys.on('chat.export', () => {
				// A download is a link being followed; the menu's own row is that link.
				const link = document.createElement('a');
				link.href = `${API}/chats/${chatId}/export.md`;
				link.download = '';
				link.click();
			}),
			keys.on('chat.delete', () => {
				// Deleting is always asked first, so the chord opens the question, not the deed.
				confirming = true;
				open = true;
			})
		];
		return () => off.forEach((undo) => undo());
	});

	function close() {
		open = false;
		confirming = false;
	}
</script>

<IconButton
	bind:ref={anchor}
	icon="more"
	label={t.chatMenu.label}
	aria-haspopup="menu"
	aria-expanded={open}
	onclick={() => (open = !open)}
/>

<Menu {open} {anchor} label={t.chatMenu.label} align="end" onclose={close}>
	{#if confirming}
		<MenuNote>{t.rail.deleteAsk}</MenuNote>
		{#if published}<MenuNote quiet>{t.rail.deleteTakes(published)}</MenuNote>{/if}
		<MenuItem
			icon="trash"
			danger
			onclick={() => {
				close();
				ondelete();
			}}>{t.rail.delete}</MenuItem
		>
		<MenuItem onclick={close}>{t.rail.cancel}</MenuItem>
	{:else}
		<MenuItem
			icon="download"
			href={`${API}/chats/${chatId}/export.md`}
			download
			external
			keyId="chat.export"
			onclick={close}>{t.rail.export}</MenuItem
		>
		<MenuItem icon="share" disabled keyId="chat.share" description={t.chatMenu.shareSoon}>
			{t.chatMenu.share}
		</MenuItem>
		<MenuSeparator />
		<MenuItem icon="trash" danger keyId="chat.delete" onclick={() => (confirming = true)}>
			{t.rail.delete}
		</MenuItem>
	{/if}
</Menu>
