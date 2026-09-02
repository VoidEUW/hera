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
	 * The bar holds two context pills side by side — one for **skills** and one for
	 * **servers** — because a pinned skill and a running MCP server change what happens to
	 * the next thing you type, and both were previously only visible two screens away in
	 * Settings. The skills pill opens the **skill picker** (ADR 5 says the model is never
	 * asked which skill applies, and this is where a person answers instead when code guesses
	 * wrong); the servers pill opens a small sheet listing what is connected, read-only,
	 * because changing the list is Settings → Servers, not something a chat owns.
	 *
	 * `/commands` are left in the text on purpose: the router strips them server-side, and a
	 * browser that also stripped them would be a second implementation of the same rule.
	 */
	import type { Profile, Provider, Server } from '$lib/api/client';
	import { isImage, read, size, type Attachment } from '$lib/attachments';
	import { t } from '$lib/i18n';
	import Select from './Select.svelte';
	import ServerSheet from './ServerSheet.svelte';
	import SkillPicker from './SkillPicker.svelte';

	interface Props {
		placeholder?: string;
		/** A turn is streaming. Swaps send for **Stop**, which is the only thing this decides —
		 * it is about something being *in flight*, not about whether you may type. */
		busy?: boolean;
		/** The composer may not take a new message: a turn is running, or a card is open waiting
		 * on you. Kept apart from `busy` because a suspended turn is not a running one, and
		 * offering **Stop** for something that already stopped is a lie about what is happening. */
		blocked?: boolean;
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
		blocked = false,
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
	let showingServers = $state(false);

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
	// Each pill counts only its own kind, so "0 servers" really means none are reachable —
	// a number that changed with every message would be noise, and a folded-together one
	// says wrong words about whichever it was not named after.
	const skillsLabel = $derived(
		pinned.length ? t.composer.skillCount(pinned.length) : t.skills.pick
	);
	const serversLabel = $derived(t.composer.serverCount(connected.length));
	const skillsDetail = $derived(pinned.join(', '));

	const model = $derived(providers.find((entry) => entry.name === activeProvider) ?? null);

	function submit() {
		if (!sendable || blocked) return;
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

{#if showingServers}
	<ServerSheet
		servers={connected}
		onclose={() => (showingServers = false)}
		onsettings={() => {
			showingServers = false;
			onsettings?.();
		}}
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
		<!-- Disabled while a turn is running or a card is open. The second case is the one that
		     matters: sending past an open card writes a fresh assistant row, and the resume
		     routes work from the latest one — so the suspended turn would be orphaned and its
		     question could never be answered. `submit()` refuses too, because a disabled field
		     is a hint and not a guarantee. -->
		<textarea
			bind:this={field}
			bind:value={text}
			{placeholder}
			{onkeydown}
			rows="1"
			disabled={blocked}
			aria-label={placeholder}
		></textarea>

		<!-- Beside the first line rather than under the bar, and gone the moment there is
		     something to send: it is the one thing here that a person needs exactly once. -->
		<!-- Gone once there is something to send, and gone while the field is closed: a hint
		     about how to send in a box you cannot type in is instructions for nothing. -->
		<span class="hint caption" class:gone={Boolean(text) || blocked}>{t.composer.hint}</span>
	</div>

	<div class="bar">
		<button class="attach" type="button" title={t.attach.add} onclick={() => picker?.click()}>
			<span class="sr-only">{t.attach.add}</span>
			<span aria-hidden="true">＋</span>
		</button>
		<input bind:this={picker} class="sr-only" type="file" multiple tabindex="-1" onchange={pick} />

		<!-- Two pills, two destinations. The skills pill opens the picker; the servers pill
		     opens the read-only sheet. They sit side by side because the two "switched on"
		     facts they report are about the same next message, not about the same thing. -->
		{#if onskills}
			<button
				class="context skills"
				type="button"
				title={skillsDetail || t.skills.pick}
				onclick={() => (picking = true)}
			>
				<span class="dot" class:idle={!pinned.length} aria-hidden="true"></span>
				{skillsLabel}
			</button>
		{/if}

		<button
			class="context servers"
			type="button"
			title={t.servers.title}
			onclick={() => (showingServers = true)}
		>
			<span class="dot" class:idle={!connected.length} aria-hidden="true"></span>
			{serversLabel}
		</button>

		{#if profiles.length > 1}
			<div class="profile">
				<Select
					choices={profiles.map((profile) => ({
						value: profile.id,
						label: profile.name,
						hint: profile.description
					}))}
					value={profileId ?? ''}
					label={t.composer.profile}
					placement="above"
					onchange={(id) => onprofile?.(id)}
				/>
			</div>
		{/if}

		{#if providers.length}
			<div class="model">
				<Select
					choices={providers.map((entry) => ({
						value: entry.name,
						label: entry.model || entry.name,
						hint: entry.base_url
					}))}
					value={activeProvider}
					label={t.composer.model}
					placement="above"
					align="end"
					title={model ? `${model.name} · ${model.base_url}` : ''}
					onchange={(name) => onmodel?.(name)}
				/>
			</div>
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
			<button class="send" type="button" disabled={!sendable || blocked} onclick={submit}>
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

	/* Kept legible rather than greyed out. Whatever was half-typed is still yours, and the
	   reason you cannot send it is a card on screen a few lines up. */
	textarea:disabled {
		color: var(--text-muted);
		cursor: default;
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

	/* Both dropdowns are `Select`, which owns the pill and the popup. They used to be a native
	   `<select>` with `appearance: none` and a chevron drawn on this element — which gave back
	   the frame and left the *list* the platform's, so opening one dropped the operating
	   system's own panel into an interface that draws everything else itself. What is left here
	   is only where they sit in the row. */
	.profile,
	.model {
		display: flex;
		align-items: center;
		min-width: 0;
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
