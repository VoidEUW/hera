<script lang="ts">
	/**
	 * The composer. Stays put, focused on load, Enter to send.
	 *
	 * The bar under the field carries, left to right: **＋** to attach a file, what is *switched
	 * on* for this turn, the **profile** she is answering as, then the **model** and send. The
	 * two dropdowns answer different questions and sit at opposite ends on purpose — a profile
	 * is who is answering, an endpoint is what she is thinking with, and ADR 2 fixes the model
	 * *family* rather than how many endpoints you may keep registered.
	 *
	 * The context pill exists because a pinned skill and a running MCP server change what
	 * happens to the next thing you type, and both were previously only visible two screens
	 * away in Settings. Clicking it opens the **skill picker**: ADR 5 says the model is never
	 * asked which skill applies, and this is where a person answers instead when code guesses
	 * wrong.
	 *
	 * `/commands` are left in the text on purpose: the router strips them server-side, and a
	 * browser that also stripped them would be a second implementation of the same rule.
	 */
	import type { Profile, Provider, Server } from '$lib/api/client';
	import { isImage, read, size, type Attachment } from '$lib/attachments';
	import { t } from '$lib/i18n';
	import SkillPicker from './SkillPicker.svelte';

	interface Props {
		placeholder?: string;
		busy?: boolean;
		autofocus?: boolean;
		profiles?: Profile[];
		profileId?: string | null;
		/** Endpoints she can answer from, and which one is active. Empty is a normal state on a
		 * fresh install and says so rather than hiding the control. */
		providers?: Provider[];
		activeProvider?: string;
		servers?: Server[];
		/** Skills pinned to this conversation. On the start screen this is the workspace's set of
		 * pending pins instead — there is no chat yet, and the answer to "use this one" is known
		 * before the question is typed, not after. */
		chatSkills?: string[] | null;
		onsend?: (text: string, attachments: Attachment[]) => void;
		onstop?: () => void;
		onprofile?: (id: string) => void;
		onmodel?: (name: string) => void;
		onsettings?: () => void;
		onskills?: (names: string[]) => void;
	}

	let {
		placeholder = t.composer.placeholder,
		busy = false,
		autofocus = false,
		profiles = [],
		profileId = null,
		providers = [],
		activeProvider = '',
		servers = [],
		chatSkills = null,
		onsend,
		onstop,
		onprofile,
		onmodel,
		onsettings,
		onskills
	}: Props = $props();

	let picking = $state(false);

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

	// What is on for the next turn. Pinned skills come from the profile answering; a project's
	// pins land here when project instructions reach the interface. Retrieval adds more per
	// turn and is deliberately not counted — this says what is *always* on, and a number that
	// changed with every message would be noise rather than state.
	// The chat's pins first, then the profile's — the same order the turn merges them in, so
	// the count on screen is the set she will actually be given.
	const pinned = $derived([
		...(chatSkills ?? []),
		...(profiles.find((entry) => entry.id === profileId)?.pinned_skills ?? []).filter(
			(name) => !(chatSkills ?? []).includes(name)
		)
	]);
	const connected = $derived(servers.filter((server) => server.connected));
	const context = $derived.by(() => {
		const parts: string[] = [];
		if (pinned.length) parts.push(t.composer.skillCount(pinned.length));
		if (connected.length) parts.push(t.composer.serverCount(connected.length));
		return parts.join(' · ');
	});
	const contextDetail = $derived(
		[pinned.join(', '), connected.map((server) => `${server.name} (${server.tools})`).join(', ')]
			.filter(Boolean)
			.join(' · ')
	);

	const model = $derived(providers.find((entry) => entry.name === activeProvider) ?? null);

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

{#if picking && onskills}
	<SkillPicker
		pinned={chatSkills ?? []}
		onclose={() => (picking = false)}
		onpick={(names) => onskills(names)}
	/>
{/if}

<div class="composer">
	{#if attached.length}
		<ul class="attached">
			{#each attached as file, index (file.name + index)}
				<li class:picture={isImage(file)}>
					<!-- The composer is the one place that still holds the bytes, so it is the one
					     place that can show the picture rather than its name. After the message is
					     sent the contents are gone from the browser on purpose and the bubble draws
					     a chip — the same chip a text file gets, which is honest about what the
					     interface knows at that point. -->
					{#if isImage(file)}
						<img src={file.data_url} alt={file.name} />
					{/if}
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

	<div class="field">
		<textarea
			bind:this={field}
			bind:value={text}
			{placeholder}
			{onkeydown}
			rows="1"
			aria-label={placeholder}
		></textarea>

		<!-- Beside the first line rather than under the bar, and gone the moment there is
		     something to send: it is the one thing here that a person needs exactly once. -->
		<span class="hint caption" class:gone={Boolean(text)}>{t.composer.hint}</span>
	</div>

	<div class="bar">
		<button class="attach" type="button" title={t.attach.add} onclick={() => picker?.click()}>
			<span class="sr-only">{t.attach.add}</span>
			<span aria-hidden="true">＋</span>
		</button>
		<input bind:this={picker} class="sr-only" type="file" multiple tabindex="-1" onchange={pick} />

		<!-- One pill, one destination: the picker. It used to fall through to Settings whenever
		     the caller had no chat to pin to, which meant the start screen answered "what is
		     switched on?" by opening a different screen about something else. -->
		{#if onskills || context}
			<button
				class="context"
				type="button"
				title={contextDetail || t.skills.pick}
				onclick={() => (onskills ? (picking = true) : onsettings?.())}
			>
				<span class="dot" class:idle={!pinned.length && !connected.length} aria-hidden="true"
				></span>
				{context || t.skills.pick}
			</button>
		{/if}

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

		{#if providers.length}
			<label class="model">
				<span class="sr-only">{t.composer.model}</span>
				<select
					value={activeProvider}
					title={model ? `${model.name} · ${model.base_url}` : ''}
					onchange={(event) => onmodel?.(event.currentTarget.value)}
				>
					{#each providers as entry (entry.name)}
						<option value={entry.name}>{entry.model || entry.name}</option>
					{/each}
				</select>
			</label>
		{:else}
			<!-- Nothing registered. Saying so where the model belongs beats an empty gap, and it
			     is one click from the screen that fixes it. -->
			<button class="nomodel" type="button" onclick={() => onsettings?.()}>
				{t.composer.noModel}
			</button>
		{/if}

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

	/* A picture keeps the chip it would have had and gains a thumbnail on the left, so a row of
	   four attachments still reads as one row of the same thing rather than two kinds of card. */
	.attached li.picture {
		padding-left: 3px;
	}

	.attached img {
		width: 26px;
		height: 26px;
		object-fit: cover;
		border-radius: 6px;
		background: var(--ground);
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

	.field {
		position: relative;
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

	.context {
		display: flex;
		align-items: center;
		gap: 6px;
		padding: 3px 9px;
		border: 1px solid var(--line);
		border-radius: 999px;
		font-size: 12.5px;
		color: var(--text-muted);
		transition:
			border-color var(--fade) var(--ease),
			color var(--fade) var(--ease);
	}

	.context:hover {
		border-color: var(--text-faint);
		color: var(--text);
	}

	/* Live state, so laurel: something is switched on for the next thing you type. Nothing on
	   is not a failure, so the dot goes quiet rather than red. */
	.dot {
		width: 6px;
		height: 6px;
		border-radius: 50%;
		background: var(--laurel);
	}

	.dot.idle {
		background: var(--text-faint);
	}

	/* Both dropdowns are drawn as the same pill the context chip is, because they sit in the
	   same row and mean the same *kind* of thing — one switch each, currently set to this. A
	   native `<select>` here brought the operating system's own border, radius and arrow into a
	   bar of hand-drawn controls, and no amount of matching the font hid that. `appearance:
	   none` gives the frame back, and the chevron below is the one part that has to be redrawn
	   by hand. The popup itself stays native and unstyleable, which is correct: it is the
	   platform's list and behaves the way that platform's lists do. */
	.profile,
	.model {
		position: relative;
		display: flex;
		align-items: center;
		min-width: 0;
	}

	.profile select,
	.model select {
		appearance: none;
		width: 100%;
		background: none;
		border: 1px solid var(--line);
		border-radius: 999px;
		padding: 3px 24px 3px 10px;
		font-size: 12.5px;
		line-height: 1.45;
		color: var(--text-muted);
		cursor: pointer;
		text-overflow: ellipsis;
		transition:
			border-color var(--fade) var(--ease),
			color var(--fade) var(--ease);
	}

	.profile select:hover,
	.model select:hover {
		border-color: var(--text-faint);
		color: var(--text);
	}

	/* The popup is the platform's, so its rows are too — but a system that has not been told
	   which end of the theme we are on paints them white. `color-scheme` on :root covers the
	   two big browsers; this covers the rest. */
	.profile option,
	.model option {
		background: var(--surface-raised);
		color: var(--text);
	}

	/* The chevron the native control is no longer drawing. Two borders on a rotated square:
	   one shape, no asset, and it takes the colour of the row like everything else here. */
	.profile::after,
	.model::after {
		content: '';
		position: absolute;
		right: 10px;
		width: 5px;
		height: 5px;
		border-right: 1.5px solid var(--text-faint);
		border-bottom: 1.5px solid var(--text-faint);
		transform: translateY(-2px) rotate(45deg);
		pointer-events: none;
	}

	.model,
	.nomodel {
		margin-left: auto;
	}

	.model {
		max-width: 22ch;
	}

	/* Dashed, because nothing is registered — the one control on this bar that is a gap rather
	   than a setting, and it should not read as a pill that happens to be empty. */
	.nomodel {
		padding: 3px 10px;
		border: 1px dashed var(--line);
		border-radius: 999px;
		font-size: 12.5px;
		color: var(--text-faint);
	}

	.nomodel:hover {
		border-color: var(--brass);
		color: var(--brass);
	}

	.hint {
		position: absolute;
		top: 4px;
		right: 0;
		pointer-events: none;
		color: var(--text-faint);
		background: var(--surface);
		padding-left: 8px;
		transition: opacity var(--fade) var(--ease);
	}

	.hint.gone {
		opacity: 0;
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

		.model {
			max-width: 12ch;
		}
	}
</style>
