<script lang="ts">
	/**
	 * The composer (the theme's `hera/composer`, soft look): a filled rounded box that takes a
	 * laurel border and ring on focus (`composer.focus`). Top to bottom: the files going with the
	 * message, the field with "Enter to send" in its corner, and the toolbar.
	 *
	 * The toolbar, left to right: **+** to attach, the **skills** chip (what is pinned for this
	 * chat, a menu of checkbox rows), the **servers** chip (what she can reach, read-only — changing
	 * the list is Settings → Servers), the **profile** when there is more than one, then at the right
	 * end the **reasoning** control this model has, the **model**, and **send**.
	 *
	 * ADR 5 says the model is never asked which skill applies — selection is code — and the skills
	 * menu is where a person answers instead when code guesses wrong. A pin here outranks the
	 * profile's and the project's, and is applied as it is clicked: a switch that needs confirming
	 * is a switch you have to remember you flipped.
	 *
	 * **Reasoning** reads and writes the active model's own options (ADR 18), in whichever shape
	 * the server says this model has (`thinking_shape`): a level picker, an on/off chip, a token
	 * budget, or nothing — global, like the model beside it.
	 *
	 * How full the context window is lives in the top bar now: it describes the chat, not the
	 * message being typed. `/commands` are left in the text on purpose: the router strips them
	 * server-side, and a browser that also stripped them would be a second implementation.
	 */
	import type { Profile, Provider, Server } from '$lib/api/client';
	import { isImage, read, size, type Attachment } from '$lib/attachments';
	import { t } from '$lib/i18n';
	import { keys } from '$lib/keys';
	import ModelSelector from './ModelSelector.svelte';
	import SkillMenu from './SkillMenu.svelte';
	import type { Tab as SettingsTab } from '$lib/settingsTabs';
	import AttachmentChip from './ui/AttachmentChip.svelte';
	import Chip from './ui/Chip.svelte';
	import FileButton from './ui/FileButton.svelte';
	import Menu from './ui/Menu.svelte';
	import MenuHeading from './ui/MenuHeading.svelte';
	import MenuItem from './ui/MenuItem.svelte';
	import MenuNote from './ui/MenuNote.svelte';
	import MenuSeparator from './ui/MenuSeparator.svelte';
	import NumberField from './ui/NumberField.svelte';
	import Selector from './ui/Selector.svelte';
	import SendButton from './ui/SendButton.svelte';
	import Textarea from './ui/Textarea.svelte';

	interface Props {
		placeholder?: string;
		/** A turn is streaming. Swaps send for **Stop**. */
		busy?: boolean;
		/** Stop was pressed and the turn has not closed yet. */
		cancelling?: boolean;
		/** The composer may not take a new message: a turn is running, or a card is open waiting on
		 * you. Kept apart from `busy` because a suspended turn is not a running one, and offering
		 * **Stop** for something that already stopped is a lie about what is happening. */
		blocked?: boolean;
		autofocus?: boolean;
		profiles?: Profile[];
		profileId?: string | null;
		providers?: Provider[];
		activeProvider?: string;
		servers?: Server[];
		/** Skills pinned to this conversation. On the start screen, the workspace's pending pins. */
		chatSkills?: string[] | null;
		onsend?: (text: string, attachments: Attachment[]) => void;
		onstop?: () => void;
		onprofile?: (id: string) => void;
		onmodel?: (providerName: string, modelId?: string) => void;
		onreasoning?: (providerName: string, modelId: string, value: string) => void;
		onthinking?: (providerName: string, modelId: string, on: boolean) => void;
		onbudget?: (providerName: string, modelId: string, tokens: number) => void;
		onsettings?: (section?: SettingsTab) => void;
		onskills?: (names: string[]) => void;
	}

	let {
		placeholder = t.composer.placeholder,
		busy = false,
		cancelling = false,
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
		onreasoning,
		onthinking,
		onbudget,
		onsettings,
		onskills
	}: Props = $props();

	let text = $state('');
	let field = $state<HTMLTextAreaElement | null>(null);
	let attached = $state<Attachment[]>([]);
	let refused = $state<string[]>([]);

	let serversOpen = $state(false);
	let serversChip = $state<HTMLButtonElement | null>(null);
	let budgetOpen = $state(false);
	let budgetChip = $state<HTMLButtonElement | null>(null);

	// Shift+Escape puts the cursor back in the message field from anywhere (#112).
	$effect(() =>
		keys.on('composer', () => {
			if (!field) return false;
			field.focus();
		})
	);

	$effect(() => {
		if (autofocus) field?.focus();
	});

	const sendable = $derived(Boolean(text.trim()) || attached.length > 0);

	// The chat's pins first, then the profile's — the same order the turn merges them in, so the
	// count on screen is the set she will actually be given.
	const profilePins = $derived(
		profiles.find((entry) => entry.id === profileId)?.pinned_skills ?? []
	);
	/** The servers a person added. Her own is in the list so the Servers screen can show it, and it
	 * is not one of these: counting it made the chip say "1 server" on a machine with none. */
	const added = $derived(servers.filter((server) => !server.builtin));
	const connected = $derived(added.filter((server) => server.connected));

	const activeEntry = $derived(providers.find((entry) => entry.name === activeProvider) ?? null);
	const activeModel = $derived(
		activeEntry?.models.find((entry) => entry.id === activeEntry.active_model) ?? null
	);

	// **One slot, whichever control this model actually has.** The server decides which, in
	// `thinking_shape`, so the composer and the settings screen cannot disagree. A model nobody
	// could ask about gets no control; the field stays writable on Settings → Models.
	const shape = $derived(activeModel?.thinking_shape ?? 'none');
	const efforts = $derived(activeModel?.reasoning_efforts ?? []);
	const reasoningChoices = $derived([
		{ value: '', label: t.composer.effort.default },
		...efforts.map((effort) => ({ value: effort, label: effort }))
	]);
	const thinkingOn = $derived(
		(activeModel?.options.chat_template_kwargs as { enable_thinking?: unknown } | undefined)
			?.enable_thinking !== false
	);
	const budget = $derived(
		typeof activeModel?.options.thinking_budget === 'number'
			? activeModel.options.thinking_budget
			: null
	);
	const reasoningValue = $derived(
		typeof activeModel?.options.reasoning_effort === 'string'
			? activeModel.options.reasoning_effort
			: ''
	);

	/** A thinking budget is a number of tokens: 0 is "do not think" and is left to the switch, and
	 * the ceiling is a number a person can read rather than one that has to be looked up. */
	const BUDGET_MIN = 256;
	const BUDGET_MAX = 32768;

	function setBudget(value: number | null) {
		if (!activeEntry || !activeModel || value === null) return;
		onbudget?.(activeEntry.name, activeModel.id, Math.min(BUDGET_MAX, Math.max(BUDGET_MIN, value)));
	}

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

	async function pick(files: FileList) {
		const picked = await read(files);
		attached = [...attached, ...picked.attachments];
		refused = picked.rejected.map((item) => item.reason);
	}
</script>

<div class="composer">
	{#if attached.length}
		<div class="attachments">
			{#each attached as file, index (file.name + index)}
				<!-- The composer is the one place that still holds the bytes, so it is the one place
				     that can show the picture rather than its name. -->
				<AttachmentChip
					name={file.name}
					size={size(file.bytes)}
					icon={isImage(file) ? 'image' : 'file'}
					thumbnail={isImage(file) ? file.data_url : undefined}
					onremove={() => (attached = attached.filter((_, at) => at !== index))}
				/>
			{/each}
		</div>
	{/if}

	{#each refused as reason (reason)}
		<p class="refused">{reason}</p>
	{/each}

	<div class="top">
		<!-- Disabled while a turn is running or a card is open. Sending past an open card writes a
		     fresh assistant row, and the resume routes work from the latest one — so the suspended
		     turn would be orphaned. `submit()` refuses too: a disabled field is a hint, not a
		     guarantee. -->
		<Textarea
			bare
			grow={160}
			bind:ref={field}
			value={text}
			{placeholder}
			ariaLabel={placeholder}
			disabled={blocked}
			{onkeydown}
			onchange={(value) => (text = value)}
		/>
		<span class="hint">{t.composer.hint}</span>
	</div>

	<div class="row">
		<FileButton label={t.attach.add} multiple onfiles={pick} />

		{#if onskills}
			<SkillMenu pinned={chatSkills ?? []} locked={profilePins} onpick={onskills} />
		{/if}

		<Chip
			bind:ref={serversChip}
			on={connected.length > 0}
			haspopup="menu"
			expanded={serversOpen}
			short={String(connected.length)}
			shortIcon="plug"
			onclick={() => (serversOpen = !serversOpen)}
		>
			{t.composer.serverCount(connected.length)}
		</Chip>
		<Menu
			open={serversOpen}
			anchor={serversChip}
			label={t.servers.title}
			placement="above"
			onclose={() => (serversOpen = false)}
		>
			<MenuHeading>{t.servers.heading}</MenuHeading>
			{#each added as server (server.name)}
				<MenuItem
					icon="plug"
					disabled
					description={`${server.tools} ${server.tools === 1 ? t.servers.toolSingular : t.servers.toolPlural} · ${server.connected ? t.servers.connected : t.servers.notConnected}`}
					>{server.name}</MenuItem
				>
			{:else}
				<MenuNote quiet>{t.servers.none}</MenuNote>
			{/each}
			<MenuSeparator />
			<MenuItem
				icon="sliders"
				onclick={() => {
					serversOpen = false;
					onsettings?.('servers');
				}}>{t.servers.configure}</MenuItem
			>
		</Menu>

		{#if profiles.length > 1}
			<Selector
				look="chip"
				icon="user"
				choices={profiles.map((profile) => ({
					value: profile.id,
					label: profile.name,
					description: profile.description
				}))}
				value={profileId ?? ''}
				label={t.composer.profile}
				short=""
				placement="above"
				onchange={(id) => onprofile?.(id)}
			/>
		{/if}

		<span class="space" aria-hidden="true"></span>

		{#if activeEntry && activeModel}
			{#if shape === 'values'}
				<Selector
					look="chip"
					icon="brain"
					choices={reasoningChoices}
					value={reasoningValue}
					label={t.composer.reasoning}
					short=""
					placement="above"
					align="end"
					onchange={(value) => onreasoning?.(activeEntry.name, activeModel.id, value)}
				/>
			{:else if shape === 'toggle'}
				<Chip
					on={thinkingOn}
					pressed={thinkingOn}
					hint={thinkingOn ? t.composer.thinkingOn : t.composer.thinkingOff}
					short=""
					shortIcon="brain"
					onclick={() => onthinking?.(activeEntry.name, activeModel.id, !thinkingOn)}
				>
					{thinkingOn ? t.composer.thinking : t.composer.thinkingOff}
				</Chip>
			{:else if shape === 'budget'}
				<Chip
					bind:ref={budgetChip}
					icon="brain"
					chevron
					haspopup="menu"
					expanded={budgetOpen}
					label={t.composer.budgetTitle}
					short=""
					onclick={() => (budgetOpen = !budgetOpen)}
				>
					{budget === null ? t.composer.effort.default : t.composer.budget(budget)}
				</Chip>
				<Menu
					open={budgetOpen}
					anchor={budgetChip}
					label={t.composer.budgetTitle}
					placement="above"
					align="end"
					onclose={() => (budgetOpen = false)}
				>
					<MenuHeading>{t.composer.budgetTitle}</MenuHeading>
					{#each [1024, 4096, 16384] as preset (preset)}
						<MenuItem
							trail="check"
							on={budget === preset}
							onclick={() => {
								setBudget(preset);
								budgetOpen = false;
							}}>{t.composer.budget(preset)}</MenuItem
						>
					{/each}
					<MenuSeparator />
					<div class="custom">
						<NumberField
							compact
							value={budget}
							min={BUDGET_MIN}
							max={BUDGET_MAX}
							step={256}
							unit={t.composer.tokens}
							ariaLabel={t.composer.budgetTitle}
							onkeydown={(event) => {
								if (event.key === 'Enter') budgetOpen = false;
							}}
							onchange={setBudget}
						/>
					</div>
				</Menu>
			{/if}
		{/if}

		<span class="model">
			<ModelSelector
				{providers}
				{activeProvider}
				onmodel={(provider, model) => onmodel?.(provider, model)}
				onsettings={() => onsettings?.('models')}
			/>
		</span>

		<SendButton
			{busy}
			{cancelling}
			disabled={!sendable || blocked}
			onsend={submit}
			onstop={() => onstop?.()}
		/>
	</div>
</div>

<style>
	.composer {
		position: relative;
		display: flex;
		flex-direction: column;
		gap: 8px;
		width: 100%;
		padding: 10px 10px 10px 14px;
		border: var(--border-width) solid var(--line);
		border-radius: var(--radius-lg);
		background: var(--surface);
		container-type: inline-size;
		transition:
			box-shadow var(--motion-composer-focus),
			border-color var(--motion-composer-focus);
	}

	/* `composer.focus`, the ring preset: a laurel border and a 3px laurel-soft ring. */
	.composer:focus-within {
		border-color: var(--laurel);
		box-shadow: 0 0 0 3px var(--laurel-soft);
	}

	.attachments {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
	}

	.refused {
		margin: 0;
		color: var(--danger);
		font-size: 12px;
	}

	.top {
		display: flex;
		align-items: flex-start;
		gap: 10px;
	}

	/* `cmp.hint: show` — "Enter to send" in the corner, at every width. */
	.hint {
		padding-top: 5px;
		color: var(--text-faint);
		font-size: 11px;
		white-space: nowrap;
	}

	@container (max-width: 420px) {
		.hint {
			display: none;
		}
	}

	.row {
		display: flex;
		align-items: center;
		gap: 6px;
		min-width: 0;
	}

	.space {
		flex: 1;
		min-width: 4px;
	}

	/* A wrapper with no box of its own on the desktop. */
	.model {
		display: contents;
	}

	/* On a phone the other chips go short (`Chip`'s `short`), and the model keeps its name: it is
	   the one a person reads before sending, so it takes the room the others gave up. */
	@media (max-width: 780px) {
		.space {
			display: none;
		}

		.model {
			display: flex;
			flex: 1 1 auto;
			justify-content: flex-end;
			min-width: 0;
		}

		.model :global(.chip) {
			max-width: 100%;
		}
	}

	.custom {
		padding: 4px 9px 6px;
	}
</style>
