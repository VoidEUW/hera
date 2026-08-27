<script lang="ts">
	/**
	 * The composer. Stays put, focused on load, Enter to send.
	 *
	 * The bar under the field carries, left to right: **＋** to attach a file, the **profile**
	 * she is answering from, and send. The dropdown is not a model picker — there is one model
	 * (ADR 2); there are many of her.
	 *
	 * `/commands` are left in the text on purpose: the router strips them server-side, and a
	 * browser that also stripped them would be a second implementation of the same rule.
	 */
	import type { Profile } from '$lib/api/client';
	import { read, size, type Attachment } from '$lib/attachments';
	import { t } from '$lib/i18n';

	interface Props {
		placeholder?: string;
		busy?: boolean;
		autofocus?: boolean;
		profiles?: Profile[];
		profileId?: string | null;
		onsend?: (text: string, attachments: Attachment[]) => void;
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
	let picker = $state<HTMLInputElement | null>(null);
	let attached = $state<Attachment[]>([]);
	let refused = $state<string[]>([]);

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

	const sendable = $derived(Boolean(text.trim()) || attached.length > 0);

	function submit() {
		if (!sendable || busy) return;
		onsend?.(text, attached);
		text = '';
		attached = [];
		refused = [];
	}

	function onkeydown(event: KeyboardEvent) {
		if (event.key !== 'Enter' || event.shiftKey || event.isComposing) return;
		event.preventDefault();
		submit();
	}

	async function pick(event: Event) {
		const input = event.currentTarget as HTMLInputElement;
		if (!input.files?.length) return;
		const picked = await read(input.files);
		attached = [...attached, ...picked.attachments];
		refused = picked.rejected.map((item) => item.reason);
		// Cleared so choosing the same file twice in a row still fires a change event.
		input.value = '';
	}

	function drop(index: number) {
		attached = attached.filter((_, at) => at !== index);
	}
</script>

<div class="composer">
	{#if attached.length}
		<ul class="attached">
			{#each attached as file, index (file.name + index)}
				<li>
					<span class="mono name">{file.name}</span>
					<span class="size">{size(file.bytes)}</span>
					<button type="button" onclick={() => drop(index)}>
						<span class="sr-only">{t.attach.remove}</span>
						<span aria-hidden="true">✕</span>
					</button>
				</li>
			{/each}
		</ul>
	{/if}

	{#each refused as reason (reason)}
		<p class="refused">{reason}</p>
	{/each}

	<textarea
		bind:this={field}
		bind:value={text}
		{placeholder}
		{onkeydown}
		rows="1"
		aria-label={placeholder}
	></textarea>

	<div class="bar">
		<button class="attach" type="button" title={t.attach.add} onclick={() => picker?.click()}>
			<span class="sr-only">{t.attach.add}</span>
			<span aria-hidden="true">＋</span>
		</button>
		<input bind:this={picker} class="sr-only" type="file" multiple tabindex="-1" onchange={pick} />

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
			<button class="send" type="button" disabled={!sendable} onclick={submit}>
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

	.attached {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
		list-style: none;
		margin: 0 0 10px;
		padding: 0;
	}

	.attached li {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 3px 6px 3px 10px;
		background: var(--surface-raised);
		border: 1px solid var(--line);
		border-radius: var(--radius);
		font-size: 12.5px;
	}

	.name {
		max-width: 22ch;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.size {
		color: var(--text-faint);
	}

	.attached button {
		color: var(--text-faint);
		font-size: 11px;
	}

	.attached button:hover {
		color: var(--danger);
	}

	.refused {
		margin: 0 0 8px;
		font-size: 12.5px;
		color: var(--danger);
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

	.attach {
		display: grid;
		place-items: center;
		width: 26px;
		height: 26px;
		flex: none;
		border-radius: 50%;
		border: 1px solid var(--line);
		color: var(--text-muted);
		font-size: 13px;
		transition:
			border-color var(--fade) var(--ease),
			color var(--fade) var(--ease);
	}

	.attach:hover {
		border-color: var(--brass);
		color: var(--brass);
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
