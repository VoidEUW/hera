<script lang="ts">
	/**
	 * A settings screen that could not load: the error page at pane size, with the way to try
	 * again. Only for the *load* — a save or a switch that fails says so beside the control it
	 * was, because the screen is still there and still right.
	 */
	import ErrorPage from '$lib/components/ui/ErrorPage.svelte';
	import { failure } from '$lib/errors';
	import { t } from '$lib/i18n';

	interface Props {
		cause: unknown;
		/** What was being loaded, in lower case: "usage". */
		what: string;
		onretry: () => void;
	}

	let { cause, what, onretry }: Props = $props();

	const shown = $derived(failure(cause, what));
	let retrying = $state(false);

	async function retry() {
		retrying = true;
		try {
			await onretry();
		} finally {
			retrying = false;
		}
	}
</script>

<ErrorPage
	size="panel"
	kind={shown.kind}
	code={shown.code}
	title={shown.title}
	body={shown.body}
	detail={shown.detail}
	primary={{ label: t.ui.retry, onclick: () => void retry(), busy: retrying }}
/>
