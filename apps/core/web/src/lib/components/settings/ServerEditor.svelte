<script lang="ts">
	/**
	 * Add a server, or change one (#108): how it is reached, what it is called, and whether it
	 * runs. Saving writes `mcp.json` and reconnects that one server; the others are not touched.
	 *
	 * The name is the entry's identity — its tools are `name__tool` and rules are written against
	 * that — so it is typed once and read-only afterwards. A secret already saved comes back as a
	 * hidden value (`servers.ts`): the field says it is set, and leaving it alone keeps it.
	 */
	import { untrack } from 'svelte';
	import { api, ApiError, type Server } from '$lib/api/client';
	import Button from '$lib/components/ui/Button.svelte';
	import Checkbox from '$lib/components/ui/Checkbox.svelte';
	import IconButton from '$lib/components/ui/IconButton.svelte';
	import Input from '$lib/components/ui/Input.svelte';
	import Modal from '$lib/components/ui/Modal.svelte';
	import Segmented from '$lib/components/ui/Segmented.svelte';
	import Textarea from '$lib/components/ui/Textarea.svelte';
	import { t } from '$lib/i18n';
	import { blank, draftOf, entryOf, missing, type Draft, type Row } from '$lib/servers';

	interface Props {
		/** The server being changed. Left out, this adds one. */
		name?: string;
		onsaved: (server: Server) => void;
		onclose: () => void;
	}

	let { name, onsaved, onclose }: Props = $props();

	/** Read once: the form belongs to the person typing in it, and a list refreshing behind must
	 * not rewrite what they have half typed. */
	const editing = untrack(() => name);
	const isNew = editing === undefined;

	let draft = $state<Draft>(blank());
	let loading = $state(!isNew);
	let saving = $state(false);
	let error = $state<string | null>(null);

	const text = (cause: unknown) =>
		cause instanceof ApiError || cause instanceof Error ? cause.message : String(cause);

	if (editing !== undefined) {
		api
			.serverConfig(editing)
			.then((entry) => (draft = draftOf(editing, entry)))
			.catch((cause) => (error = text(cause)))
			.finally(() => (loading = false));
	}

	const kinds = [
		{ value: 'stdio' as const, label: t.serverEditor.stdio },
		{ value: 'http' as const, label: t.serverEditor.http }
	];

	const lacking = $derived(missing(draft));
	const why = $derived(
		lacking === 'name'
			? t.serverEditor.needName
			: lacking === 'command'
				? t.serverEditor.needCommand
				: lacking === 'url'
					? t.serverEditor.needUrl
					: null
	);

	async function save() {
		if (lacking) {
			error = why;
			return;
		}
		saving = true;
		error = null;
		try {
			onsaved(await api.saveServer(draft.name.trim(), entryOf(draft)));
		} catch (cause) {
			error = text(cause);
		} finally {
			saving = false;
		}
	}

	function edit(list: Row[], index: number, change: Partial<Row>): Row[] {
		return list.map((row, at) => (at === index ? { ...row, ...change } : row));
	}
</script>

{#snippet pairs(label: string, help: string, list: Row[], set: (next: Row[]) => void)}
	<fieldset class="pairs">
		<legend class="label">{label}</legend>
		<p class="caption">{help}</p>
		{#each list as row, index (index)}
			<div class="pair">
				<Input
					mono
					ariaLabel={`${label}: ${t.serverEditor.key}`}
					placeholder={t.serverEditor.key}
					value={row.key}
					onchange={(key) => set(edit(list, index, { key }))}
				/>
				<Input
					mono
					kind="password"
					ariaLabel={`${label}: ${t.serverEditor.value}`}
					placeholder={row.hidden ? t.serverEditor.hiddenValue : t.serverEditor.value}
					value={row.value}
					onchange={(value) => set(edit(list, index, { value, hidden: false }))}
				/>
				<IconButton
					icon="trash"
					size="sm"
					label={t.serverEditor.removeRow}
					onclick={() => set(list.filter((_, at) => at !== index))}
				/>
			</div>
		{/each}
		<div>
			<Button
				variant="ghost"
				size="sm"
				icon="plus"
				onclick={() => set([...list, { key: '', value: '', hidden: false }])}
			>
				{t.serverEditor.addRow}
			</Button>
		</div>
	</fieldset>
{/snippet}

<Modal
	label={isNew ? t.serverEditor.newServer : t.serverEditor.editServer}
	title={isNew ? t.serverEditor.newServer : t.serverEditor.editServer}
	placement="top"
	width="min(600px, 94vw)"
	{onclose}
>
	<div class="body" aria-busy={loading}>
		<Input
			mono
			label={t.serverEditor.name}
			help={isNew ? t.serverEditor.nameHelp : t.serverEditor.nameLocked}
			placeholder={t.serverEditor.namePlaceholder}
			value={draft.name}
			disabled={!isNew || loading}
			autofocus={isNew}
			onchange={(value) => (draft.name = value)}
		/>

		<div class="kind">
			<span class="label">{t.serverEditor.kindLabel}</span>
			<Segmented
				options={kinds}
				value={draft.kind}
				label={t.serverEditor.kindLabel}
				onchange={(next) => (draft.kind = next)}
			/>
			<p class="caption">{t.serverEditor.kindHelp[draft.kind]}</p>
		</div>

		{#if draft.kind === 'stdio'}
			<Input
				mono
				label={t.serverEditor.command}
				placeholder={t.serverEditor.commandPlaceholder}
				value={draft.command}
				disabled={loading}
				onchange={(value) => (draft.command = value)}
			/>
			<Textarea
				mono
				label={t.serverEditor.args}
				help={t.serverEditor.argsHelp}
				placeholder={t.serverEditor.argsPlaceholder}
				rows={3}
				value={draft.args}
				onchange={(value) => (draft.args = value)}
			/>
			{@render pairs(
				t.serverEditor.env,
				t.serverEditor.envHelp,
				draft.env,
				(next) => (draft.env = next)
			)}
			<Input
				mono
				label={t.serverEditor.cwd}
				help={t.serverEditor.cwdHelp}
				value={draft.cwd}
				onchange={(value) => (draft.cwd = value)}
			/>
		{:else}
			<Input
				kind="url"
				mono
				label={t.serverEditor.url}
				placeholder={t.serverEditor.urlPlaceholder}
				value={draft.url}
				disabled={loading}
				onchange={(value) => (draft.url = value)}
			/>
			{@render pairs(
				t.serverEditor.headers,
				t.serverEditor.headersHelp,
				draft.headers,
				(next) => (draft.headers = next)
			)}
		{/if}

		<Checkbox
			variant="switch"
			label={t.serverEditor.enabled}
			description={t.serverEditor.enabledHelp}
			checked={draft.enabled}
			onchange={(on) => (draft.enabled = on)}
		/>

		{#if error}<p class="error" role="alert">{error}</p>{/if}
	</div>

	{#snippet footer()}
		<Button variant="ghost" onclick={onclose}>{t.serverEditor.cancel}</Button>
		<Button variant="highlighted" busy={saving} disabled={loading || !!lacking} onclick={save}>
			{isNew ? t.serverEditor.create : t.serverEditor.save}
		</Button>
	{/snippet}
</Modal>

<style>
	.body {
		display: flex;
		flex-direction: column;
		gap: 16px;
		padding: 8px 22px 18px;
		overflow-y: auto;
	}

	.label {
		display: block;
		margin-bottom: 6px;
		font-size: 13px;
	}

	.caption {
		margin: 6px 0 0;
	}

	.pairs {
		margin: 0;
		padding: 0;
		border: 0;
	}

	.pairs .label {
		padding: 0;
	}

	.pair {
		display: grid;
		grid-template-columns: 1fr 1.4fr auto;
		align-items: center;
		gap: 8px;
		margin-top: 8px;
	}

	.error {
		margin: 0;
		color: var(--danger);
		font-size: 13px;
	}
</style>
