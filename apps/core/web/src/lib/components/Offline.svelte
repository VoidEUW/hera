<script lang="ts">
	/**
	 * Nothing answered, so there is nothing to draw: the screen that replaces the application
	 * when the very first load never landed.
	 *
	 * Instead of the shell rather than over it — no rail, no profile, no conversation — because
	 * every control in those needs the server that is not answering. What it offers is what a
	 * person can actually do: start the server (the command, one click to copy), try again, and
	 * read what the browser said if they need to.
	 */
	import { t } from '$lib/i18n';
	import { workspace } from '$lib/stores/workspace.svelte';
	import ErrorPage from './ui/ErrorPage.svelte';
</script>

<ErrorPage
	kind="offline"
	title={t.offline.title}
	body={t.offline.body}
	command={{ text: t.offline.command, hint: t.offline.commandHint }}
	primary={{
		label: workspace.retrying ? t.error.retrying : t.error.retry,
		busy: workspace.retrying,
		onclick: () => workspace.retry()
	}}
	detail={workspace.error ? { label: t.offline.detail, text: workspace.error } : undefined}
/>
