<script lang="ts">
	/**
	 * Every primitive in `lib/components/ui/`, in every state, on one page (#182).
	 *
	 * Not linked from anywhere: it is for the person changing a theme or a primitive, who should
	 * be able to see the whole set at once in both modes rather than hunting for the one screen
	 * that happens to use a switch. The `capture` job films it, so a pull request that changes a
	 * token shows what it did to everything. It follows the theme export's own component order.
	 *
	 * The words here are fixtures, not interface copy, which is why they are not in `$lib/i18n`.
	 * The components with no backend yet — Voice call, Image generation, Sign in — live only here.
	 */
	import AttachmentChip from '$lib/components/ui/AttachmentChip.svelte';
	import Auth from '$lib/components/ui/Auth.svelte';
	import Avatar from '$lib/components/ui/Avatar.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import Checkbox from '$lib/components/ui/Checkbox.svelte';
	import Chip from '$lib/components/ui/Chip.svelte';
	import CloseButton from '$lib/components/ui/CloseButton.svelte';
	import CodeView from '$lib/components/ui/CodeView.svelte';
	import Collapsible from '$lib/components/ui/Collapsible.svelte';
	import ContextMeter from '$lib/components/ui/ContextMeter.svelte';
	import FileEditor from '$lib/components/ui/FileEditor.svelte';
	import Icon from '$lib/components/ui/Icon.svelte';
	import IconButton from '$lib/components/ui/IconButton.svelte';
	import ImageGen from '$lib/components/ui/ImageGen.svelte';
	import Input from '$lib/components/ui/Input.svelte';
	import Kbd from '$lib/components/ui/Kbd.svelte';
	import NumberField from '$lib/components/ui/NumberField.svelte';
	import Ocellus from '$lib/components/ui/Ocellus.svelte';
	import Pill from '$lib/components/ui/Pill.svelte';
	import ProgressBar from '$lib/components/ui/ProgressBar.svelte';
	import SearchBar from '$lib/components/ui/SearchBar.svelte';
	import Segmented from '$lib/components/ui/Segmented.svelte';
	import Selector from '$lib/components/ui/Selector.svelte';
	import SendButton from '$lib/components/ui/SendButton.svelte';
	import Skeleton from '$lib/components/ui/Skeleton.svelte';
	import Slider from '$lib/components/ui/Slider.svelte';
	import Spinner from '$lib/components/ui/Spinner.svelte';
	import StallBox from '$lib/components/ui/StallBox.svelte';
	import Swatches from '$lib/components/ui/Swatches.svelte';
	import Textarea from '$lib/components/ui/Textarea.svelte';
	import Thinking from '$lib/components/ui/Thinking.svelte';
	import TraceRow from '$lib/components/ui/TraceRow.svelte';
	import VoiceCall from '$lib/components/ui/VoiceCall.svelte';
	import { ICONS, type IconName } from '$lib/icons';
	import { theme, type Appearance } from '$lib/theme.svelte';
	import { toasts } from '$lib/toasts.svelte';

	const variants = [
		'neutral',
		'highlighted',
		'signature',
		'danger',
		'danger-soft',
		'ghost'
	] as const;
	const names = Object.keys(ICONS) as IconName[];

	const SOURCE = `import { reveal } from '$lib/motion';

export function arrive(node: HTMLElement) {
    // A comment, a string, a number.
    return reveal(node, { scale: 0.95, slot: 'menu-enter' });
}
`;

	const SKILL = `---
name: frontend-design
description: Use when building a page that should not look templated.
---

Pick a direction before writing a line of CSS.
`;

	/** A small picture to stand in for an image she made: a gradient, as an SVG data URL. */
	const PICTURE =
		'data:image/svg+xml;utf8,' +
		encodeURIComponent(
			`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 100"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f2c64e"/><stop offset="1" stop-color="#6fb3f2"/></linearGradient></defs><rect width="160" height="100" fill="url(#g)"/></svg>`
		);

	let text = $state('you@example.com');
	let notes = $state('');
	let budget = $state<number | null>(4096);
	let query = $state('');
	let model = $state('apodex');
	let on = $state(true);
	let off = $state(false);
	let level = $state(0.4);
	let tab = $state<'preview' | 'source'>('preview');
	let open = $state(true);
	let skills = $state(true);
	let colour = $state('laurel');
	let busy = $state(false);
	let muted = $state(false);
	let traceOpen = $state(false);
	let skillSource = $state(SKILL);
</script>

<svelte:head><title>Design — Hera</title></svelte:head>

<main class="gallery">
	<header>
		<h1 class="display">Hera — components</h1>
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
		<h2>Navigation · search, selector, segmented, tooltip</h2>
		<div class="grid">
			<SearchBar
				value={query}
				placeholder="Search chats"
				shortcut="⌘K"
				onchange={(v) => (query = v)}
			/>
			<Selector
				label="Model"
				icon="cube"
				value={model}
				choices={[
					{
						value: 'apodex',
						label: 'Apodex 1.1',
						description: 'apodex/apodex-1.1-mini:free',
						group: 'Local',
						icon: 'cube'
					},
					{
						value: 'qwen',
						label: 'Qwen3 14B',
						description: 'LM Studio · Mac Mini',
						group: 'Local',
						icon: 'cube'
					},
					{
						value: 'claude',
						label: 'Claude Sonnet 5.5',
						description: 'Anthropic API',
						group: 'Remote',
						icon: 'cube'
					}
				]}
				onchange={(value) => (model = value)}
			/>
		</div>
		<div class="row">
			<Selector
				look="chip"
				label="Model"
				icon="cube"
				value={model}
				choices={[
					{ value: 'apodex', label: 'Apodex 1.1', group: 'Local', icon: 'cube' },
					{ value: 'qwen', label: 'Qwen3 14B', group: 'Local', icon: 'cube' },
					{ value: 'claude', label: 'Claude Sonnet 5.5', group: 'Remote', icon: 'cube' }
				]}
				onchange={(value) => (model = value)}
			/>
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
			<IconButton icon="info" label="A tooltip, after a rest" />
			<ContextMeter used={6200} limit={32768} />
			<ContextMeter used={19800} limit={32768} />
			<ContextMeter used={30100} limit={32768} />
		</div>
	</section>

	<section>
		<h2>Actions · buttons, icon buttons, close</h2>
		{#each ['md', 'sm', 'lg'] as const as size (size)}
			<div class="row">
				{#each variants as variant (variant)}
					<Button {variant} {size}>{variant}</Button>
				{/each}
				<Button {size} disabled>Grayed out</Button>
				<Button {size} variant="signature" icon="arrowUp">Send</Button>
				<Button {size} busy>Working</Button>
			</div>
		{/each}
		<div class="row">
			<IconButton icon="copy" label="Copy" />
			<IconButton icon="check" label="Copied" on />
			<IconButton icon="more" label="More" size="sm" />
			<IconButton icon="plus" label="Attach" bordered />
			<CloseButton size="sm" />
			<CloseButton />
			<CloseButton size="lg" />
			<Button onclick={() => toasts.show('Copied')}>Show a toast</Button>
			<Button variant="danger-soft" onclick={() => toasts.fail('Could not save — no answer')}>
				Show a failure
			</Button>
		</div>
	</section>

	<section>
		<h2>Inputs · fields, toggles, collapsible</h2>
		<div class="grid">
			<Input
				label="Email"
				kind="email"
				value={text}
				help="Where the link goes."
				onchange={(v) => (text = v)}
			/>
			<Input
				label="Base URL"
				value="localhost:1234"
				error="That is not a URL."
				onchange={() => {}}
			/>
			<Input value="" placeholder="Disabled" ariaLabel="Disabled" disabled />
			<NumberField
				label="Thinking budget"
				unit="tokens"
				value={budget}
				onchange={(v) => (budget = v)}
			/>
			<Textarea label="Notes" value={notes} maxlength={200} onchange={(v) => (notes = v)} />
			<Swatches
				label="Colour"
				value={colour}
				swatches={[
					{ value: '', label: 'Plain', colour: 'var(--text-faint)' },
					{ value: 'brass', label: 'Brass', colour: 'var(--brass)' },
					{ value: 'laurel', label: 'Laurel', colour: 'var(--laurel)' },
					{ value: 'pomegranate', label: 'Pomegranate', colour: 'var(--pomegranate)' }
				]}
				onchange={(v) => (colour = v)}
			/>
		</div>
		<div class="row">
			<Checkbox checked={on} label="Checked" onchange={(value) => (on = value)} />
			<Checkbox checked={off} label="Unchecked" onchange={(value) => (off = value)} />
			<Checkbox
				checked={on}
				variant="switch"
				label="Switch"
				description="With a description"
				onchange={(value) => (on = value)}
			/>
			<Checkbox checked={false} variant="switch" label="Disabled" disabled />
		</div>
		<div class="row slider">
			<Slider
				value={level}
				min={0}
				max={1}
				step={0.01}
				ariaLabel="Level"
				onchange={(v) => (level = v)}
			/>
		</div>
		<Collapsible bind:open>
			{#snippet title()}local{/snippet}
			{#snippet subtitle()}http://localhost:1234/v1{/snippet}
			{#snippet actions()}<Pill tone="authority">active</Pill>{/snippet}
			<p>The body, kept in the document while shut so a field inside keeps its value.</p>
		</Collapsible>
	</section>

	<section>
		<h2>Marks · chips, pills, avatar, keys</h2>
		<div class="row">
			<Pill>neutral</Pill>
			<Pill tone="live">running</Pill>
			<Pill tone="authority">pinned</Pill>
			<Pill tone="danger">failed</Pill>
			<Chip on={skills} pressed={skills} onclick={() => (skills = !skills)}>1 skill</Chip>
			<Chip>0 servers</Chip>
			<Kbd>⌘K</Kbd>
			<Avatar name="Void" />
			<Avatar />
			<AttachmentChip name="brief.pdf" size="184 KB" />
			<AttachmentChip
				name="screenshot.png"
				icon="image"
				thumbnail={PICTURE}
				progress={0.62}
				onremove={() => {}}
			/>
		</div>
	</section>

	<section>
		<h2>Feedback · loading, stalled, bars, skeleton</h2>
		<div class="row">
			<Spinner size={14} />
			<Spinner size={20} label="Loading the model" />
			<Spinner size={28} />
			<Spinner size={20} stalled label="Not responding" />
		</div>
		<div class="stack">
			<StallBox title="Loading Apodex 1.1" seconds={4} />
			<StallBox
				title="Loading Apodex 1.1"
				seconds={32}
				stalled
				onwait={() => {}}
				onretry={() => {}}
			/>
			<ProgressBar label="Determinate" value={0.6} />
			<ProgressBar label="Indeterminate" />
			<ProgressBar label="Thick, danger" value={0.92} thick tone="danger" meter />
		</div>
		<Skeleton rows={3} />
	</section>

	<section>
		<h2>Conversation · ocellus, thinking, trace</h2>
		<div class="row">
			<Ocellus size={28} />
			<Ocellus size={22} />
			<Ocellus size={16} />
			<Ocellus size={8} />
			<Ocellus size={28} closed />
			<Thinking />
		</div>
		<div class="trace">
			<TraceRow verb="thought" text="68 words" toggle bind:open={traceOpen}>
				{#snippet body()}<p>A thought, opened.</p>{/snippet}
			</TraceRow>
			<TraceRow
				state="done"
				verb="called"
				text="artifact create programmer-portfolio.html"
				meta="9 ms"
			/>
			<TraceRow state="live" verb="called" text="web search “cream palettes”" meta="running…" />
			<TraceRow state="failed" verb="called" text="shell run rm -rf build" meta="denied" loud />
		</div>
		<div class="row">
			<SendButton busy={false} onsend={() => (busy = true)} onstop={() => (busy = false)} />
			<SendButton {busy} onsend={() => (busy = true)} onstop={() => (busy = false)} />
			<SendButton busy disabled onsend={() => {}} onstop={() => {}} />
			<SendButton busy cancelling onsend={() => {}} onstop={() => {}} />
		</div>
		<div class="frame">
			<VoiceCall seconds={7} {muted} onmute={() => (muted = !muted)} onend={() => {}} />
		</div>
		<div class="row">
			<ImageGen state="queued" prompt="Dunes at sunset, a warm hero sketch" />
			<ImageGen state="generating" prompt="Dunes at sunset" src={PICTURE} step={18} />
			<ImageGen state="done" prompt="Dunes at sunset" src={PICTURE} summary="3.3 s · 1280 x 800" />
			<ImageGen
				state="failed"
				prompt="Dunes at sunset"
				src={PICTURE}
				step={14}
				reason="The image model ran out of memory."
				onretry={() => {}}
			/>
		</div>
	</section>

	<section>
		<h2>Files · code view, file editor</h2>
		<div class="frame code">
			<CodeView text={SOURCE} extension="ts" name="motion.ts" />
		</div>
		<div class="editor">
			<FileEditor
				kind="skill"
				name="frontend-design/SKILL.md"
				meta="Skill · 1.2 KB"
				text={skillSource}
				onchange={(v) => (skillSource = v)}
			>
				{#snippet footer()}
					<span>Read only · turn on Edit to change it</span>
					<Pill tone="authority">verified</Pill>
				{/snippet}
			</FileEditor>
		</div>
		<div class="editor">
			<FileEditor kind="image" name="dunes.png" meta="PNG · 160 x 100" src={PICTURE} />
		</div>
	</section>

	<section>
		<h2>Sign in / Register</h2>
		<Auth />
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
		gap: calc(var(--space) * 4);
		margin-bottom: calc(var(--space) * 4);
	}

	.slider {
		max-width: 320px;
	}

	.stack {
		display: flex;
		flex-direction: column;
		gap: calc(var(--space) * 3);
		max-width: 420px;
		margin-bottom: calc(var(--space) * 4);
	}

	.trace {
		max-width: var(--column);
		margin-bottom: calc(var(--space) * 4);
	}

	.frame {
		max-width: var(--column);
		margin-bottom: calc(var(--space) * 4);
		padding: 10px 14px;
		border: var(--border-width) solid var(--line);
		border-radius: var(--radius-lg);
		background: var(--surface);
	}

	.frame.code {
		padding: 0;
		overflow: hidden;
		border-radius: var(--radius-sm);
	}

	.editor {
		height: 320px;
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
