<script lang="ts">
	/**
	 * A file going with a message (a Hera addition to `hera/composer`'s attachments, the builder's
	 * `.att`): an icon or a thumbnail, the name, the size — or "uploading" with a 2px laurel bar
	 * along the bottom edge while it is — and a small × when it can still be taken off.
	 *
	 * The same chip shows a sent message's files, without the ×, so a file looks the same before
	 * and after it went.
	 */
	import type { IconName } from '$lib/icons';
	import { t } from '$lib/i18n';
	import CloseButton from './CloseButton.svelte';
	import Icon from './Icon.svelte';

	interface Props {
		name: string;
		/** "184 KB". Omitted while uploading. */
		size?: string;
		icon?: IconName;
		/** An image's own picture, drawn small instead of the icon. */
		thumbnail?: string;
		/** 0 to 1 while uploading. */
		progress?: number;
		onremove?: () => void;
		onopen?: () => void;
	}

	let { name, size, icon = 'file', thumbnail, progress, onremove, onopen }: Props = $props();
	const uploading = $derived(progress !== undefined && progress < 1);
</script>

<span class="attachment" class:uploading>
	{#if onopen}
		<button class="open" type="button" onclick={onopen}>
			{@render body()}
		</button>
	{:else}
		{@render body()}
	{/if}
	{#if onremove}<CloseButton size="sm" label={t.ui.remove(name)} onclick={onremove} />{/if}
	{#if progress !== undefined}
		<span
			class="bar"
			role="progressbar"
			aria-label={name}
			aria-valuemin={0}
			aria-valuemax={100}
			aria-valuenow={Math.round(progress * 100)}
			style:--value={progress}><i></i></span
		>
	{/if}
</span>

{#snippet body()}
	{#if thumbnail}
		<img class="thumbnail" src={thumbnail} alt="" />
	{:else}
		<span class="icon"><Icon name={icon} /></span>
	{/if}
	<span class="name">{name}</span>
	{#if uploading}<small>{t.ui.uploading}</small>{:else if size}<small>{size}</small>{/if}
{/snippet}

<style>
	.attachment {
		position: relative;
		display: inline-flex;
		align-items: center;
		gap: 8px;
		max-width: 220px;
		padding: 5px 4px 5px 8px;
		overflow: hidden;
		border: var(--border-width) solid var(--line);
		border-radius: var(--radius-sm);
		background: var(--surface-raised);
		font-size: 12px;
	}

	.open {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		min-width: 0;
		text-align: left;
	}

	.icon {
		display: inline-grid;
		color: var(--text-muted);
	}

	.thumbnail {
		flex: none;
		width: 22px;
		height: 22px;
		border-radius: 4px;
		object-fit: cover;
	}

	.name {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	small {
		color: var(--text-faint);
		font-size: 11px;
		white-space: nowrap;
	}

	.bar {
		position: absolute;
		right: 0;
		bottom: 0;
		left: 0;
		height: 2px;
	}

	.bar i {
		position: absolute;
		inset: 0 auto 0 0;
		width: calc(var(--value) * 100%);
		background: var(--laurel);
		transition: width var(--motion-bar-indeterminate);
	}
</style>
