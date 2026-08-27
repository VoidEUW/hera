<script lang="ts">
	/**
	 * The composer. Stays put, focused on load, Enter to send.
	 *
	 * The dropdown is the **profile** — the mind she is answering from — not a model picker.
	 * There is one model (ADR 2); there are many of her.
	 *
	 * `/commands` are left in the text on purpose: the router strips them server-side, and a
	 * browser that also stripped them would be a second implementation of the same rule.
	 */
	import type { Profile } from '$lib/api/client';
	import { t } from '$lib/i18n';

	interface Props {
		placeholder?: string;
		busy?: boolean;
		autofocus?: boolean;
		profiles?: Profile[];
		profileId?: string | null;
		onsend?: (text: string) => void;
		onstop?: () => void;
		onprofile?: (id: string) => void;
	}

	let {
		placeholder = t.composer.placeholder,
		busy = false,
		autofocus = false,
		profiles = [],
		profileId = null,
		onsend,
		onstop,
		onprofile
	}: Props = $props();

	let text = $state('');
	let field = $state<HTMLTextAreaElement | null>(null);

	$effect(() => {
		if (autofocus) field?.focus();
	});

	// Grow with the content up to a ceiling, so a long message is visible without the composer
	// taking the whole screen.
	$effect(() => {
		if (!field) return;
		void text;
		field.style.height = 'auto';
		field.style.height = `${Math.min(field.scrollHeight, 260)}px`;
	});

	function submit() {
		const value = text.trim();
		if (!value || busy) return;
		onsend?.(value);
		text = '';
	}

	function onkeydown(event: KeyboardEvent) {
		if (event.key !== 'Enter' || event.shiftKey || event.isComposing) return;
		event.preventDefault();
		submit();
	}
</script>

<div class="composer">
	<textarea
		bind:this={field}
		bind:value={text}
		{placeholder}
		{onkeydown}
		rows="1"
		aria-label={placeholder}
	></textarea>

	<div class="bar">
		{#if profiles.length > 1}
			<label class="profile">
				<span class="sr-only">Profile</span>
				<select
					value={profileId ?? ''}
					onchange={(event) => onprofile?.(event.currentTarget.value)}
				>
					{#each profiles as profile (profile.id)}
						<option value={profile.id}>{profile.name}</option>
					{/each}
				</select>
			</label>
		{/if}

		<span class="hint caption">{t.composer.hint}</span>

		{#if busy}
			<button class="send stop" type="button" onclick={() => onstop?.()}>{t.composer.stop}</button>
		{:else}
			<button class="send" type="button" disabled={!text.trim()} onclick={submit}>
				<span class="sr-only">{t.composer.send}</span>
				<span aria-hidden="true">↑</span>
			</button>
		{/if}
	</div>
</div>

<style>
	.composer {
		background: var(--surface);
		border: 1px solid var(--line);
		border-radius: var(--radius-lg);
		padding: 12px 14px 10px;
		transition: border-color var(--fade) var(--ease);
	}

	.composer:focus-within {
		border-color: var(--text-faint);
	}

	textarea {
		display: block;
		width: 100%;
		border: 0;
		background: none;
		resize: none;
		font-family: var(--font-body);
		font-size: 16px;
		line-height: 1.55;
		max-height: 260px;
		overflow-y: auto;
	}

	textarea:focus {
		outline: none;
	}

	textarea::placeholder {
		color: var(--text-faint);
	}

	.bar {
		display: flex;
		align-items: center;
		gap: 10px;
		margin-top: 8px;
	}

	.profile select {
		background: none;
		border: 1px solid var(--line);
		border-radius: var(--radius);
		padding: 3px 6px;
		font-size: 12.5px;
		color: var(--text-muted);
	}

	.hint {
		margin-left: auto;
		color: var(--text-faint);
	}

	.send {
		display: grid;
		place-items: center;
		width: 30px;
		height: 30px;
		border-radius: 50%;
		background: var(--pomegranate);
		color: var(--ground);
		font-size: 15px;
		transition: opacity var(--fade) var(--ease);
	}

	.send:disabled {
		opacity: 0.35;
		cursor: default;
	}

	.stop {
		width: auto;
		padding: 0 12px;
		border-radius: var(--radius);
		font-size: 13px;
	}

	@media (max-width: 640px) {
		.hint {
			display: none;
		}

		.send {
			margin-left: auto;
		}
	}
</style>
