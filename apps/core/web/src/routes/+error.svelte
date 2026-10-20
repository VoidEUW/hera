<script lang="ts">
	/**
	 * Where the router lands when a screen could not be drawn (#140, #141): an address that leads
	 * nowhere, or something that threw on the way.
	 *
	 * Inside the shell, so the sidebar is still there and the way out is the way you came in. A
	 * not-found is said as a fact about the address rather than as an alarm; anything else says
	 * what to try and keeps what happened one click away for whoever has to report it.
	 */
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import ErrorPage from '$lib/components/ui/ErrorPage.svelte';
	import { t } from '$lib/i18n';

	const missing = $derived(page.status === 404);
</script>

<svelte:head><title>{missing ? t.notFound.title : t.broken.title} — Hera</title></svelte:head>

{#if missing}
	<ErrorPage
		kind="not-found"
		title={t.notFound.title}
		body={t.notFound.body}
		primary={{ label: t.notFound.home, onclick: () => goto(resolve('/')) }}
	/>
{:else}
	<ErrorPage
		kind="server"
		title={t.broken.title}
		body={t.broken.body}
		primary={{ label: t.broken.reload, onclick: () => location.reload() }}
		secondary={{ label: t.broken.home, onclick: () => goto(resolve('/')) }}
		detail={page.error?.message
			? { label: t.broken.detail, text: `${page.status} · ${page.error.message}` }
			: undefined}
	/>
{/if}
