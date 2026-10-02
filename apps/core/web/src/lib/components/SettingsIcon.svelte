<script lang="ts">
	/**
	 * The mark beside each entry in the settings sidebar.
	 *
	 * One component and one set, drawn on the same 16-unit grid with the stroke `Wrench.svelte`
	 * and the gutter marks use, so the sidebar reads as part of the same hand. Drawn rather than
	 * pulled from an icon package: there is none in this project, and nine paths do not justify
	 * adding one.
	 */
	export type SettingsIconName =
		'general' | 'mind' | 'memory' | 'models' | 'dreaming' | 'skills' | 'servers' | 'permissions';

	interface Props {
		name: SettingsIconName;
		size?: number;
	}

	let { name, size = 16 }: Props = $props();

	const PATHS: Record<SettingsIconName, string[]> = {
		// Three sliders.
		general: [
			'M2 4h5.6 M12.4 4H14',
			'M10 2.6a1.4 1.4 0 1 0 0 2.8 1.4 1.4 0 0 0 0-2.8z',
			'M2 8h1.6 M8.4 8H14',
			'M6 6.6a1.4 1.4 0 1 0 0 2.8 1.4 1.4 0 0 0 0-2.8z',
			'M2 12h6.6 M13.4 12H14',
			'M11 10.6a1.4 1.4 0 1 0 0 2.8 1.4 1.4 0 0 0 0-2.8z'
		],
		// Two hemispheres and the fissure between them, as `Brain.svelte` draws them.
		mind: [
			'M8 3.2v9.6',
			'M8 3.2C7 2.2 4.8 2.4 4 4c-1.3.3-1.9 1.9-1.1 3-.8 1.1-.3 2.8 1 3.1.2 1.4 1.7 2.2 2.8 1.6.2.2.8.1 1.3-.2',
			'M8 3.2c1-1 3.2-.8 4 .8 1.3.3 1.9 1.9 1.1 3 .8 1.1.3 2.8-1 3.1-.2 1.4-1.7 2.2-2.8 1.6-.2.2-.8.1-1.3-.2'
		],
		// A clock face turning back.
		memory: ['M2.6 8a5.4 5.4 0 1 0 1.6-3.8', 'M2.4 2.6v2.2h2.2', 'M8 5v3.2l2 1.2'],
		// A cube.
		models: ['M8 1.8 13.6 5v6L8 14.2 2.4 11V5z', 'M2.6 5 8 8.2 13.4 5', 'M8 8.2v6'],
		// A crescent moon.
		dreaming: ['M12.8 9.6A5.4 5.4 0 0 1 6.4 3.2a5.4 5.4 0 1 0 6.4 6.4z'],
		// A scroll.
		skills: [
			'M4.5 2.5h7a1.5 1.5 0 0 1 1.5 1.5v8.5',
			'M4.5 2.5A1.5 1.5 0 0 0 3 4v8a1.5 1.5 0 0 0 1.5 1.5H11',
			'M11 13.5a2 2 0 0 0 2-2H8.5',
			'M6 6h4 M6 8.5h3'
		],
		// A plug.
		servers: ['M6 2v3 M10 2v3', 'M4.5 5h7v2.5a3.5 3.5 0 0 1-7 0z', 'M8 11v3'],
		// A shield.
		permissions: [
			'M8 1.8 13 3.6v4.2c0 3-2.1 5.1-5 6.4-2.9-1.3-5-3.4-5-6.4V3.6z',
			'M5.8 8l1.5 1.5L10.4 6.4'
		]
	};
</script>

<svg
	width={size}
	height={size}
	viewBox="0 0 16 16"
	fill="none"
	stroke="currentColor"
	stroke-width="1.6"
	stroke-linecap="round"
	stroke-linejoin="round"
	aria-hidden="true"
>
	{#each PATHS[name] as d (d)}
		<path {d} />
	{/each}
</svg>

<style>
	svg {
		display: block;
		flex: none;
	}
</style>
