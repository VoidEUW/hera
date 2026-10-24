<script lang="ts">
	/**
	 * One tool of a server: its name, what it does, and a box that says whether she has it (#108).
	 *
	 * Unchecked is a `deny` rule on exactly this tool, so it also shows under Permissions, and she
	 * is not offered it at all. When a *wider* rule is what turned it off (`fs__*`), the row says so
	 * — checking the box then writes an exact allow beside that rule, which wins by being more
	 * specific, and the rest stay off.
	 */
	import type { ServerTool } from '$lib/api/client';
	import Checkbox from '$lib/components/ui/Checkbox.svelte';
	import { t } from '$lib/i18n';

	interface Props {
		tool: ServerTool;
		busy?: boolean;
		onchange: (allowed: boolean) => void;
	}

	let { tool, busy = false, onchange }: Props = $props();
</script>

<div class="tool" class:off={!tool.allowed}>
	<div class="text">
		<span class="name">{tool.local_name}</span>
		{#if tool.description}<p class="caption described">
				{tool.description}
			</p>{/if}
		{#if !tool.allowed && tool.rule && !tool.exact}
			<p class="caption wider">{t.serverEditor.deniedBy(tool.rule)}</p>
		{/if}
	</div>
	<Checkbox
		checked={tool.allowed}
		disabled={busy}
		ariaLabel={tool.local_name}
		onchange={(allowed) => onchange(allowed)}
	/>
</div>

<style>
	.tool {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 16px;
		padding: 10px 0;
		border-top: var(--border-width) solid var(--line);
	}

	.text {
		min-width: 0;
	}

	.name {
		font-family: var(--font-mono);
		font-size: 13px;
	}

	.off .name {
		color: var(--text-muted);
		text-decoration: line-through;
	}

	.caption {
		margin: 2px 0 0;
	}

	/* Her own tools carry paragraphs of prompt text as their descriptions; three lines say what a
	   tool is for. */
	.described {
		display: -webkit-box;
		overflow: hidden;
		-webkit-box-orient: vertical;
		-webkit-line-clamp: 3;
		line-clamp: 3;
	}

	.wider {
		color: var(--text-muted);
	}
</style>
