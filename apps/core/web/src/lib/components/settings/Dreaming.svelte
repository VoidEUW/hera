<script lang="ts">
	/**
	 * Dreaming is listed and not built: a v0.3 feature you can see coming is a promise, and one
	 * you cannot is a surprise.
	 */
	import { t } from '$lib/i18n';
</script>

<p class="empty">{t.settings.dreamingSoon}</p>

<style>
	.empty {
		margin: 18px 0;
		max-width: 60ch;
		font-family: var(--font-body);
		font-size: 15px;
		line-height: 1.6;
		color: var(--text-muted);
	}
</style>
