<script lang="ts">
	/**
	 * The start screen: mark, greeting, composer. Nothing else.
	 *
	 * The greeting is the one place the display face gets to be large, and the one place her
	 * voice is heard before she has said anything.
	 *
	 * Sending from here opens a chat and navigates into it, carrying the message — so the first
	 * thing a person types is never lost to a page transition.
	 */
	import { goto } from '$app/navigation';
	import Composer from '$lib/components/Composer.svelte';
	import Ocellus from '$lib/components/Ocellus.svelte';
	import { greetingFor, t } from '$lib/i18n';
	import { workspace } from '$lib/stores/workspace.svelte';

	let busy = $state(false);
	let error = $state<string | null>(null);

	const greeting = greetingFor();

	async function start(text: string) {
		busy = true;
		error = null;
		const chat = await workspace.createChat();
		if (!chat) {
			busy = false;
			error = workspace.error ?? t.error.send;
			return;
		}
		// Handed over through the store rather than a query string: a message is not a URL, and
		// a refresh must not send it a second time.
		workspace.handOff(text);
		await goto(`/chat/${chat.id}`);
	}
</script>

<div class="start">
	<div class="middle">
		<p class="greeting display">
			<Ocellus size={26} />
			<span>{greeting}</span>
		</p>

		<Composer autofocus {busy} profiles={workspace.profiles} onsend={start} />

		{#if error}
			<p class="error">{error}</p>
		{/if}
	</div>
</div>

<style>
	.start {
		display: grid;
		place-items: center;
		height: 100%;
		padding: 24px;
	}

	.middle {
		width: min(720px, 100%);
		margin-bottom: 8vh;
	}

	.greeting {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 12px;
		margin: 0 0 26px;
		font-size: 40px;
		line-height: 1.15;
	}

	.error {
		margin: 12px 0 0;
		color: var(--danger);
		font-size: 13px;
		text-align: center;
	}
</style>
