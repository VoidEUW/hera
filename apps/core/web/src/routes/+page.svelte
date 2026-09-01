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
	import type { Attachment } from '$lib/attachments';
	import Composer from '$lib/components/Composer.svelte';
	import Ocellus from '$lib/components/Ocellus.svelte';
	import { greetingFor, t } from '$lib/i18n';
	import { workspace } from '$lib/stores/workspace.svelte';

	let busy = $state(false);
	let error = $state<string | null>(null);

	const greeting = greetingFor();

	async function start(text: string, files: Attachment[]) {
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
		workspace.handOff(text, files);
		await goto(`/chat/${chat.id}`);
	}
</script>

<div class="start">
	<div class="middle">
		<p class="greeting display">
			<Ocellus size={26} />
			<span>{greeting}</span>
		</p>

		<Composer
			autofocus
			{busy}
			profiles={workspace.profiles}
			profileId={workspace.activeProfile?.id ?? null}
			providers={workspace.providers}
			activeProvider={workspace.activeProvider}
			servers={workspace.servers}
			chatSkills={workspace.pendingSkills}
			onsend={start}
			onmodel={(name) => workspace.useProvider(name)}
			onsettings={() => workspace.openSettings()}
			onskills={(names) => (workspace.pendingSkills = names)}
		/>

		{#if error}
			<p class="error">{error}</p>
		{/if}
	</div>

	<!-- Under the composer, centred, and quiet enough to be furniture. The start screen is the
	     one page with room for it and the one people look at while wondering whether the thing
	     they just pulled is the thing they are running. -->
	{#if workspace.version}
		<p class="version caption">{t.settings.version(workspace.version)}</p>
	{/if}
</div>

<style>
	.start {
		position: relative;
		display: grid;
		place-items: center;
		height: 100%;
		padding: 24px;
		padding-bottom: max(24px, env(safe-area-inset-bottom));
	}

	/* Pinned to the foot of the screen rather than trailing the composer, so it does not move
	   when the greeting or an error changes the height of the column above it. */
	.version {
		position: absolute;
		bottom: max(18px, env(safe-area-inset-bottom));
		left: 50%;
		transform: translateX(-50%);
		margin: 0;
		color: var(--text-faint);
	}

	/* The same column the conversation uses, so the composer does not change width when the
	   first message turns this screen into that one. */
	.middle {
		width: min(var(--column), 100%);
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
