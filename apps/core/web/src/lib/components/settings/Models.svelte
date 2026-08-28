<script lang="ts">
	/**
	 * Where she runs.
	 *
	 * The first screen a person needs, because nothing else in Hera does anything until she is
	 * pointed at a model — and until now there was no way to do it without an environment
	 * variable and a restart.
	 *
	 * **Test before you commit to it.** The endpoint is asked what models it has, and the answer
	 * either fills a dropdown or says plainly why it could not. "Nothing is listening on that
	 * port" is the commonest thing to be wrong on a fresh install, and it belongs on the screen
	 * you are already looking at.
	 *
	 * **The key is write-only.** It never comes back from the API, so an empty field means
	 * "leave what is stored alone". Saying so under the field is the difference between that
	 * being a sensible rule and a trap.
	 */
	import { api, type Probe, type Provider } from '$lib/api/client';
	import { t } from '$lib/i18n';

	interface Props {
		filter?: string;
	}

	let { filter = '' }: Props = $props();

	let providers = $state<Provider[]>([]);
	let active = $state('');
	let error = $state<string | null>(null);
	let saved = $state<string | null>(null);
	let probes = $state<Record<string, Probe | 'running'>>({});
	let adding = $state(false);

	// One draft per endpoint, so typing in a field does not fight the list refreshing under it.
	let drafts = $state<Record<string, Partial<Provider> & { api_key?: string }>>({});
	let fresh = $state({ name: '', base_url: 'http://localhost:1234/v1', model: '', api_key: '' });

	const shown = $derived(
		providers.filter(
			(p) => !filter || `${p.name} ${p.base_url} ${p.model}`.toLowerCase().includes(filter)
		)
	);

	$effect(() => {
		void load();
	});

	async function load() {
		try {
			const body = await api.providers();
			providers = body.providers;
			active = body.active;
			drafts = Object.fromEntries(body.providers.map((p) => [p.name, {}]));
			error = null;
		} catch (cause) {
			error = say(cause);
		}
	}

	function apply(body: { providers: Provider[]; active: string }) {
		providers = body.providers;
		active = body.active;
	}

	async function save(entry: Provider) {
		const patch = drafts[entry.name] ?? {};
		if (Object.keys(patch).length === 0) return;
		try {
			apply(await api.updateProvider(entry.name, patch));
			drafts = { ...drafts, [entry.name]: {} };
			saved = entry.name;
			setTimeout(() => (saved = null), 1600);
		} catch (cause) {
			error = say(cause);
		}
	}

	async function add() {
		try {
			apply(await api.addProvider({ ...fresh }));
			fresh = { name: '', base_url: 'http://localhost:1234/v1', model: '', api_key: '' };
			adding = false;
			error = null;
		} catch (cause) {
			error = say(cause);
		}
	}

	async function probe(name: string) {
		probes = { ...probes, [name]: 'running' };
		try {
			probes = { ...probes, [name]: await api.probeProvider(name) };
		} catch (cause) {
			probes = { ...probes, [name]: { ok: false, models: [], error: say(cause) } };
		}
	}

	function edit(name: string, field: string, value: string | number) {
		drafts = { ...drafts, [name]: { ...drafts[name], [field]: value } };
	}

	function current(entry: Provider, field: 'base_url' | 'model' | 'embedding_model'): string {
		const draft = drafts[entry.name]?.[field];
		return draft !== undefined ? String(draft) : entry[field];
	}

	/** The silence budget, in seconds, as the field shows it.
	 *
	 * Kept as a number all the way to the request rather than sent as a string: the API validates
	 * it as one, and a `""` from an emptied field would be a 422 saying "input should be a valid
	 * number" under a box the person had merely cleared to retype. An unparseable value falls
	 * back to what is stored, so clearing the field and clicking away changes nothing. */
	function seconds(entry: Provider): number {
		const draft = drafts[entry.name]?.timeout_s;
		return typeof draft === 'number' ? draft : entry.timeout_s;
	}

	function say(cause: unknown): string {
		return cause instanceof Error ? cause.message : String(cause);
	}
</script>

<p class="blurb">{t.models.blurb}</p>

{#if error}
	<p class="error">{error}</p>
{/if}

{#each shown as entry (entry.name)}
	{@const result = probes[entry.name]}
	<section class="entry" class:current={entry.name === active}>
		<header>
			<h3>{entry.name}</h3>
			{#if entry.name === active}
				<span class="badge">{t.models.active}</span>
			{:else}
				<button
					class="ghost"
					type="button"
					onclick={async () => apply(await api.activateProvider(entry.name))}
				>
					{t.models.activate}
				</button>
			{/if}
		</header>

		<label>
			<span>{t.models.baseUrl}</span>
			<input
				value={current(entry, 'base_url')}
				oninput={(e) => edit(entry.name, 'base_url', e.currentTarget.value)}
			/>
		</label>

		<label>
			<span>{t.models.model}</span>
			<input
				value={current(entry, 'model')}
				oninput={(e) => edit(entry.name, 'model', e.currentTarget.value)}
			/>
		</label>

		<label>
			<span>{t.models.apiKey}</span>
			<input
				type="password"
				placeholder={entry.api_key_set ? '••••••••' : ''}
				value={drafts[entry.name]?.api_key ?? ''}
				oninput={(e) => edit(entry.name, 'api_key', e.currentTarget.value)}
			/>
			<small>{entry.api_key_set ? t.models.keyStored : t.models.keyBlank}</small>
		</label>

		<label>
			<span>{t.models.embeddingModel}</span>
			<input
				value={current(entry, 'embedding_model')}
				oninput={(e) => edit(entry.name, 'embedding_model', e.currentTarget.value)}
			/>
			<small>{t.models.embeddingHint}</small>
		</label>

		<label>
			<span>{t.models.timeout}</span>
			<input
				type="number"
				min="1"
				step="10"
				value={seconds(entry)}
				oninput={(e) => {
					const parsed = Number(e.currentTarget.value);
					if (Number.isFinite(parsed) && parsed > 0) edit(entry.name, 'timeout_s', parsed);
				}}
			/>
			<small>{t.models.timeoutHint}</small>
		</label>

		<div class="actions">
			<button
				class="primary"
				type="button"
				disabled={Object.keys(drafts[entry.name] ?? {}).length === 0}
				onclick={() => save(entry)}
			>
				{t.settings.save}
			</button>
			<button class="ghost" type="button" onclick={() => probe(entry.name)}>
				{result === 'running' ? t.models.testing : t.models.test}
			</button>
			{#if saved === entry.name}
				<span class="ok">{t.models.saved}</span>
			{/if}
			<button
				class="ghost danger"
				type="button"
				onclick={async () => apply(await api.deleteProvider(entry.name))}
			>
				{t.models.remove}
			</button>
		</div>

		{#if result && result !== 'running'}
			{#if result.ok}
				<p class="ok">{t.models.reachable(result.models.length)}</p>
				<ul class="models">
					{#each result.models as name (name)}
						<li>
							<code>{name}</code>
							<button
								class="ghost tiny"
								type="button"
								onclick={() => edit(entry.name, 'model', name)}
							>
								{t.models.pick}
							</button>
						</li>
					{/each}
				</ul>
			{:else}
				<p class="error">{t.models.unreachable} — {result.error}</p>
			{/if}
		{/if}
	</section>
{:else}
	<p class="empty">{t.models.none}</p>
{/each}

{#if adding}
	<section class="entry adding">
		<h3>{t.models.add}</h3>
		<label>
			<span>{t.models.name}</span>
			<input bind:value={fresh.name} placeholder="studio" />
			<small>{t.models.nameRule}</small>
		</label>
		<label>
			<span>{t.models.baseUrl}</span>
			<input bind:value={fresh.base_url} />
		</label>
		<label>
			<span>{t.models.model}</span>
			<input bind:value={fresh.model} placeholder="qwen3.6-35b" />
		</label>
		<label>
			<span>{t.models.apiKey}</span>
			<input type="password" bind:value={fresh.api_key} />
			<small>{t.models.keyBlank}</small>
		</label>
		<div class="actions">
			<button class="primary" type="button" disabled={!fresh.name || !fresh.model} onclick={add}>
				{t.models.add}
			</button>
			<button class="ghost" type="button" onclick={() => (adding = false)}>Cancel</button>
		</div>
	</section>
{:else}
	<button class="ghost add" type="button" onclick={() => (adding = true)}>
		<span aria-hidden="true">＋</span>
		{t.models.add}
	</button>
{/if}

<style>
	.blurb,
	.empty {
		margin: 0 0 16px;
		max-width: 60ch;
		font-family: var(--font-body);
		font-size: 15px;
		line-height: 1.6;
		color: var(--text-muted);
	}

	.entry {
		padding: 16px 0;
		border-bottom: 1px solid var(--line);
	}

	.entry.current header h3 {
		color: var(--brass);
	}

	header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
		margin-bottom: 10px;
	}

	h3 {
		margin: 0;
		font-size: 14px;
		font-weight: 500;
	}

	.badge {
		font-size: 11px;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--brass);
	}

	label {
		display: block;
		margin-bottom: 10px;
	}

	label > span {
		display: block;
		font-size: 12.5px;
		color: var(--text-muted);
		margin-bottom: 3px;
	}

	input {
		width: 100%;
		padding: 7px 10px;
		background: var(--surface);
		border: 1px solid var(--line);
		border-radius: var(--radius);
		font-family: var(--font-mono);
		font-size: 13px;
	}

	small {
		display: block;
		margin-top: 3px;
		font-size: 12px;
		color: var(--text-faint);
	}

	.actions {
		display: flex;
		align-items: center;
		gap: 8px;
		margin-top: 12px;
		flex-wrap: wrap;
	}

	button {
		padding: 5px 12px;
		border: 1px solid var(--line);
		border-radius: var(--radius);
		font-size: 13px;
		color: var(--text-muted);
		transition:
			border-color var(--fade) var(--ease),
			color var(--fade) var(--ease);
	}

	button:not(:disabled):hover {
		border-color: var(--text-faint);
		color: var(--text);
	}

	button:disabled {
		opacity: 0.4;
		cursor: default;
	}

	.primary {
		border-color: var(--brass);
		color: var(--brass);
	}

	.danger:not(:disabled):hover {
		border-color: var(--danger);
		color: var(--danger);
	}

	.tiny {
		padding: 1px 8px;
		font-size: 12px;
	}

	.add {
		margin-top: 16px;
	}

	.models {
		list-style: none;
		margin: 8px 0 0;
		padding: 0;
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
	}

	.models li {
		display: flex;
		align-items: center;
		gap: 6px;
		padding: 3px 6px 3px 10px;
		background: var(--surface);
		border: 1px solid var(--line);
		border-radius: var(--radius);
	}

	code {
		font-family: var(--font-mono);
		font-size: 12.5px;
	}

	.ok {
		font-size: 12.5px;
		color: var(--laurel);
	}

	.error {
		margin: 8px 0 0;
		font-size: 12.5px;
		color: var(--danger);
	}
</style>
