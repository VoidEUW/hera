<script lang="ts">
	/**
	 * Every primitive in `lib/components/ui/`, in every state, on one page (#182).
	 *
	 * Not linked from anywhere: it is for the person changing a theme or a primitive, who should
	 * be able to see the whole set at once in both modes rather than hunting for the one screen
	 * that happens to use a switch. The `capture` job films it, so a pull request that changes a
	 * token shows what it did to everything.
	 *
	 * The words here are fixtures, not interface copy, which is why they are not in `$lib/i18n`.
	 */
	import Avatar from '$lib/components/ui/Avatar.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import Checkbox from '$lib/components/ui/Checkbox.svelte';
	import Chip from '$lib/components/ui/Chip.svelte';
	import CloseButton from '$lib/components/ui/CloseButton.svelte';
	import Collapsible from '$lib/components/ui/Collapsible.svelte';
	import Icon from '$lib/components/ui/Icon.svelte';
	import Input from '$lib/components/ui/Input.svelte';
	import Kbd from '$lib/components/ui/Kbd.svelte';
	import Pill from '$lib/components/ui/Pill.svelte';
	import ProgressBar from '$lib/components/ui/ProgressBar.svelte';
	import Segmented from '$lib/components/ui/Segmented.svelte';
	import Select from '$lib/components/ui/Select.svelte';
	import Skeleton from '$lib/components/ui/Skeleton.svelte';
	import Slider from '$lib/components/ui/Slider.svelte';
	import Spinner from '$lib/components/ui/Spinner.svelte';
	import Textarea from '$lib/components/ui/Textarea.svelte';
	import { ICONS, type IconName } from '$lib/icons';
	import { theme, type Appearance } from '$lib/theme.svelte';
	import { toasts } from '$lib/toasts.svelte';
	import { tooltip } from '$lib/tooltip';

	const variants = [
		'neutral',
		'highlighted',
		'signature',
		'danger',
		'danger-soft',
		'ghost'
	] as const;
	const names = Object.keys(ICONS) as IconName[];

	let text = $state('you@example.com');
	let notes = $state('');
	let model = $state('apodex');
	let on = $state(true);
	let off = $state(false);
	let level = $state(0.4);
	let tab = $state<'preview' | 'source'>('preview');
	let open = $state(true);
	let skills = $state(true);
</script>

<svelte:head><title>Design — Hera</title></svelte:head>

<main class="gallery">
	<header>
		<h1 class="display">Hera — primitives</h1>
		<Segmented
			label="Appearance"
			value={theme.appearance}
			options={[
				{ value: 'system', label: 'System' },
				{ value: 'light', label: 'Light', icon: 'sun' },
				{ value: 'dark', label: 'Dark', icon: 'moon' }
			]}
			onchange={(next: Appearance) => theme.set(next)}
		/>
	</header>

	<section>
		<h2>Type</h2>
		<p class="display sample-display">She sees everything.</p>
		<p class="prose">
			I’ll build the portfolio in cream, ink and caramel, with <em>one</em> accent.
		</p>
		<p>New chat · Choose skills · 0 servers · Settings</p>
		<p class="mono">artifact create programmer-portfolio.html</p>
	</section>

	<section>
		<h2>Buttons</h2>
		{#each ['md', 'sm', 'lg'] as const as size (size)}
			<div class="row">
				{#each variants as variant (variant)}
					<Button {variant} {size}>{variant}</Button>
				{/each}
				<Button {size} disabled>Grayed out</Button>
				<Button {size} icon="copy" label="Copy" />
				<Button {size} variant="highlighted" icon="arrowUp">With icon</Button>
			</div>
		{/each}
		<div class="row">
			<CloseButton size="sm" />
			<CloseButton />
			<CloseButton size="lg" />
			<span use:tooltip={'A tooltip, after a rest'}><Button icon="info" label="Tooltip" /></span>
			<Button onclick={() => toasts.show('Copied')}>Show a toast</Button>
			<Button variant="danger-soft" onclick={() => toasts.fail('Could not save — no answer')}>
				Show a failure
			</Button>
		</div>
	</section>

	<section>
		<h2>Fields</h2>
		<div class="grid">
			<Input value={text} ariaLabel="Email" onchange={(value) => (text = value)} />
			<Input value="" placeholder="Disabled" ariaLabel="Disabled" disabled />
			<Select
				field
				label="Model"
				value={model}
				choices={[
					{ value: 'apodex', label: 'Apodex 1.1' },
					{ value: 'qwen', label: 'Qwen3.6-35B' }
				]}
				onchange={(value) => (model = value)}
			/>
			<Textarea
				value={notes}
				maxlength={200}
				ariaLabel="Notes"
				onchange={(value) => (notes = value)}
			/>
		</div>
		<div class="row">
			<Checkbox checked={on} label="Checked" onchange={(value) => (on = value)} />
			<Checkbox checked={off} label="Unchecked" onchange={(value) => (off = value)} />
			<Checkbox checked={on} variant="switch" label="Switch" onchange={(value) => (on = value)} />
			<Checkbox checked={false} variant="switch" label="Disabled" disabled />
		</div>
		<div class="row slider">
			<Slider
				value={level}
				min={0}
				max={1}
				step={0.01}
				ariaLabel="Level"
				onchange={(value) => (level = value)}
			/>
		</div>
		<div class="row">
			<Segmented
				label="View"
				value={tab}
				options={[
					{ value: 'preview', label: 'Preview', icon: 'eye' },
					{ value: 'source', label: 'Source', icon: 'code' }
				]}
				onchange={(next) => (tab = next)}
			/>
			<Segmented
				size="sm"
				label="Small"
				value={tab}
				options={[
					{ value: 'preview', label: 'Preview' },
					{ value: 'source', label: 'Source' }
				]}
				onchange={(next) => (tab = next)}
			/>
		</div>
	</section>

	<section>
		<h2>Marks</h2>
		<div class="row">
			<Pill>neutral</Pill>
			<Pill tone="live">running</Pill>
			<Pill tone="authority">pinned</Pill>
			<Pill tone="danger">failed</Pill>
			<Chip on={skills} pressed={skills} onclick={() => (skills = !skills)}>1 skill</Chip>
			<Chip>0 servers</Chip>
			<Kbd>⌘</Kbd><Kbd>K</Kbd>
			<Avatar name="Void" />
			<Avatar />
		</div>
	</section>

	<section>
		<h2>Waiting</h2>
		<div class="row">
			<Spinner size={14} />
			<Spinner label="Loading the model" />
			<Spinner size={28} stalled />
		</div>
		<div class="stack">
			<ProgressBar label="Determinate" value={0.6} />
			<ProgressBar label="Indeterminate" />
			<ProgressBar label="Thick" value={0.3} thick />
		</div>
		<Skeleton rows={3} />
	</section>

	<section>
		<h2>Disclosure</h2>
		<Collapsible bind:open>
			{#snippet title()}local{/snippet}
			{#snippet subtitle()}http://localhost:1234/v1{/snippet}
			{#snippet actions()}<Pill tone="authority">active</Pill>{/snippet}
			<p>The body, kept in the document while shut so a field inside keeps its value.</p>
		</Collapsible>
	</section>

	<section>
		<h2>Icons</h2>
		<ul class="icons">
			{#each names as name (name)}
				<li><Icon {name} /><span class="mono">{name}</span></li>
			{/each}
		</ul>
	</section>
</main>

<style>
	.gallery {
		display: flex;
		flex-direction: column;
		gap: calc(var(--space) * 10);
		max-width: 960px;
		height: 100%;
		margin: 0 auto;
		padding: calc(var(--space) * 10) calc(var(--space) * 6);
		overflow-y: auto;
	}

	header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: calc(var(--space) * 4);
	}

	h1 {
		margin: 0;
		font-size: 32px;
	}

	h2 {
		margin: 0 0 calc(var(--space) * 4);
		color: var(--text-faint);
		font-size: 11px;
		font-weight: 600;
		letter-spacing: 0.09em;
		text-transform: uppercase;
	}

	section > p {
		margin: 0 0 calc(var(--space) * 2);
	}

	.sample-display {
		font-size: 28px;
	}

	.row {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: calc(var(--space) * 3);
		margin-bottom: calc(var(--space) * 4);
	}

	.grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: calc(var(--space) * 3);
		margin-bottom: calc(var(--space) * 4);
	}

	.slider {
		max-width: 320px;
	}

	.stack {
		display: flex;
		flex-direction: column;
		gap: calc(var(--space) * 3);
		max-width: 320px;
		margin-bottom: calc(var(--space) * 4);
	}

	.icons {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
		gap: calc(var(--space) * 2);
		margin: 0;
		padding: 0;
		list-style: none;
		color: var(--text-muted);
	}

	.icons li {
		display: flex;
		align-items: center;
		gap: calc(var(--space) * 2);
		font-size: 12px;
	}
</style>
