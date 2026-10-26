/**
 * The icon set (ADR 21): one stroke family on a 24-unit grid, drawn at `--icon-size` with
 * `--icon-stroke`, round caps and joins, in `currentColor`. `Icon.svelte` is the only thing that
 * draws one; the names are the theme spec's (`docs/themes/hera-theme-heaven.md` § Icons), plus
 * `brain` (Settings → Mind), `menu` (the phone's rail toggle) and `help` (a question she asks)
 * from the same family.
 *
 * The drawings are Lucide's (lucide-static v1.60.0), copied as data rather than installed: the
 * spec's stroke style is Lucide's, and a runtime icon library would be one more dependency for
 * fifty shapes. Lucide is ISC-licensed:
 *
 *   Copyright (c) Lucide Icons and Contributors. Permission to use, copy, modify, and/or distribute
 *   this software for any purpose with or without fee is hereby granted, provided that the above
 *   copyright notice and this permission notice appear in all copies.
 *
 * Each icon is a list of `[element, attributes]`, rendered with `<svelte:element>` — never as
 * markup through `{@html}`.
 */

export type IconPart = [string, Record<string, string>];

export const ICONS = {
	plus: [
		['path', { d: 'M5 12h14' }],
		['path', { d: 'M12 5v14' }]
	],
	x: [
		['path', { d: 'M18 6 6 18' }],
		['path', { d: 'm6 6 12 12' }]
	],
	search: [
		['path', { d: 'm21 21-4.34-4.34' }],
		['circle', { cx: '11', cy: '11', r: '8' }]
	],
	sliders: [
		['path', { d: 'M10 5H3' }],
		['path', { d: 'M12 19H3' }],
		['path', { d: 'M14 3v4' }],
		['path', { d: 'M16 17v4' }],
		['path', { d: 'M21 12h-9' }],
		['path', { d: 'M21 19h-5' }],
		['path', { d: 'M21 5h-7' }],
		['path', { d: 'M8 10v4' }],
		['path', { d: 'M8 12H3' }]
	],
	chat: [
		[
			'path',
			{
				d: 'M22 17a2 2 0 0 1-2 2H6.828a2 2 0 0 0-1.414.586l-2.202 2.202A.71.71 0 0 1 2 21.286V5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2z'
			}
		]
	],
	folder: [
		[
			'path',
			{
				d: 'M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z'
			}
		]
	],
	file: [
		[
			'path',
			{
				d: 'M6 22a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.704.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2z'
			}
		],
		['path', { d: 'M14 2v5a1 1 0 0 0 1 1h5' }]
	],
	download: [
		['path', { d: 'M12 15V3' }],
		['path', { d: 'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4' }],
		['path', { d: 'm7 10 5 5 5-5' }]
	],
	copy: [
		['rect', { width: '14', height: '14', x: '8', y: '8', rx: '2', ry: '2' }],
		['path', { d: 'M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2' }]
	],
	edit: [
		[
			'path',
			{
				d: 'M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z'
			}
		],
		['path', { d: 'm15 5 4 4' }]
	],
	refresh: [
		['path', { d: 'M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8' }],
		['path', { d: 'M21 3v5h-5' }],
		['path', { d: 'M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16' }],
		['path', { d: 'M8 16H3v5' }]
	],
	more: [
		['circle', { cx: '12', cy: '12', r: '1' }],
		['circle', { cx: '19', cy: '12', r: '1' }],
		['circle', { cx: '5', cy: '12', r: '1' }]
	],
	chevD: [['path', { d: 'm6 9 6 6 6-6' }]],
	chevU: [['path', { d: 'm18 15-6-6-6 6' }]],
	chevR: [['path', { d: 'm9 18 6-6-6-6' }]],
	check: [['path', { d: 'M20 6 9 17l-5-5' }]],
	clip: [
		[
			'path',
			{
				d: 'm16 6-8.414 8.586a2 2 0 0 0 2.829 2.829l8.414-8.586a4 4 0 1 0-5.657-5.657l-8.379 8.551a6 6 0 1 0 8.485 8.485l8.379-8.551'
			}
		]
	],
	mic: [
		['path', { d: 'M12 19v3' }],
		['path', { d: 'M19 10v2a7 7 0 0 1-14 0v-2' }],
		['rect', { x: '9', y: '2', width: '6', height: '13', rx: '3' }]
	],
	micOff: [
		['path', { d: 'M12 19v3' }],
		['path', { d: 'M15 9.34V5a3 3 0 0 0-5.68-1.33' }],
		['path', { d: 'M16.95 16.95A7 7 0 0 1 5 12v-2' }],
		['path', { d: 'M18.89 13.23A7 7 0 0 0 19 12v-2' }],
		['path', { d: 'm2 2 20 20' }],
		['path', { d: 'M9 9v3a3 3 0 0 0 5.12 2.12' }]
	],
	voice: [
		['path', { d: 'M2 10v3' }],
		['path', { d: 'M6 6v11' }],
		['path', { d: 'M10 3v18' }],
		['path', { d: 'M14 8v7' }],
		['path', { d: 'M18 5v13' }],
		['path', { d: 'M22 10v3' }]
	],
	spark: [
		[
			'path',
			{
				d: 'M11.017 2.814a1 1 0 0 1 1.966 0l1.051 5.558a2 2 0 0 0 1.594 1.594l5.558 1.051a1 1 0 0 1 0 1.966l-5.558 1.051a2 2 0 0 0-1.594 1.594l-1.051 5.558a1 1 0 0 1-1.966 0l-1.051-5.558a2 2 0 0 0-1.594-1.594l-5.558-1.051a1 1 0 0 1 0-1.966l5.558-1.051a2 2 0 0 0 1.594-1.594z'
			}
		],
		['path', { d: 'M20 2v4' }],
		['path', { d: 'M22 4h-4' }],
		['circle', { cx: '4', cy: '20', r: '2' }]
	],
	plug: [
		['path', { d: 'M12 22v-5' }],
		['path', { d: 'M15 8V2' }],
		['path', { d: 'M17 8a1 1 0 0 1 1 1v4a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V9a1 1 0 0 1 1-1z' }],
		['path', { d: 'M9 8V2' }]
	],
	arrowUp: [
		['path', { d: 'm5 12 7-7 7 7' }],
		['path', { d: 'M12 19V5' }]
	],
	stop: [['rect', { width: '18', height: '18', x: '3', y: '3', rx: '2' }]],
	wrench: [
		[
			'path',
			{
				d: 'M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.106-3.105c.32-.322.863-.22.983.218a6 6 0 0 1-8.259 7.057l-7.91 7.91a1 1 0 0 1-2.999-3l7.91-7.91a6 6 0 0 1 7.057-8.259c.438.12.54.662.219.984z'
			}
		]
	],
	globe: [
		['circle', { cx: '12', cy: '12', r: '10' }],
		['path', { d: 'M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20' }],
		['path', { d: 'M2 12h20' }]
	],
	clock: [
		['circle', { cx: '12', cy: '12', r: '10' }],
		['path', { d: 'M12 6v6l4 2' }]
	],
	code: [
		['path', { d: 'm16 18 6-6-6-6' }],
		['path', { d: 'm8 6-6 6 6 6' }]
	],
	image: [
		['rect', { width: '18', height: '18', x: '3', y: '3', rx: '2', ry: '2' }],
		['circle', { cx: '9', cy: '9', r: '2' }],
		['path', { d: 'm21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21' }]
	],
	user: [
		['path', { d: 'M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2' }],
		['circle', { cx: '12', cy: '7', r: '4' }]
	],
	key: [
		[
			'path',
			{
				d: 'M2.586 17.414A2 2 0 0 0 2 18.828V21a1 1 0 0 0 1 1h3a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h1a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h.172a2 2 0 0 0 1.414-.586l.814-.814a6.5 6.5 0 1 0-4-4z'
			}
		],
		['circle', { cx: '16.5', cy: '7.5', r: '.5', fill: 'currentColor' }]
	],
	keyboard: [
		['path', { d: 'M10 8h.01' }],
		['path', { d: 'M12 12h.01' }],
		['path', { d: 'M14 8h.01' }],
		['path', { d: 'M16 12h.01' }],
		['path', { d: 'M18 8h.01' }],
		['path', { d: 'M6 8h.01' }],
		['path', { d: 'M7 16h10' }],
		['path', { d: 'M8 12h.01' }],
		['rect', { x: '2', y: '4', width: '20', height: '16', rx: '2' }]
	],
	mail: [
		['path', { d: 'm22 7-8.991 5.727a2 2 0 0 1-2.009 0L2 7' }],
		['rect', { x: '2', y: '4', width: '20', height: '16', rx: '2' }]
	],
	moon: [
		[
			'path',
			{
				d: 'M20.985 12.486a9 9 0 1 1-9.473-9.472c.405-.022.617.46.402.803a6 6 0 0 0 8.268 8.268c.344-.215.825-.004.803.401'
			}
		]
	],
	sun: [
		['circle', { cx: '12', cy: '12', r: '4' }],
		['path', { d: 'M12 2v2' }],
		['path', { d: 'M12 20v2' }],
		['path', { d: 'm4.93 4.93 1.41 1.41' }],
		['path', { d: 'm17.66 17.66 1.41 1.41' }],
		['path', { d: 'M2 12h2' }],
		['path', { d: 'M20 12h2' }],
		['path', { d: 'm6.34 17.66-1.41 1.41' }],
		['path', { d: 'm19.07 4.93-1.41 1.41' }]
	],
	panel: [
		['rect', { width: '18', height: '18', x: '3', y: '3', rx: '2' }],
		['path', { d: 'M9 3v18' }]
	],
	panelR: [
		['rect', { width: '18', height: '18', x: '3', y: '3', rx: '2' }],
		['path', { d: 'M15 3v18' }]
	],
	eye: [
		[
			'path',
			{
				d: 'M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0'
			}
		],
		['circle', { cx: '12', cy: '12', r: '3' }]
	],
	external: [
		['path', { d: 'M15 3h6v6' }],
		['path', { d: 'M10 14 21 3' }],
		['path', { d: 'M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6' }]
	],
	trash: [
		['path', { d: 'M10 11v6' }],
		['path', { d: 'M14 11v6' }],
		['path', { d: 'M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6' }],
		['path', { d: 'M3 6h18' }],
		['path', { d: 'M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2' }]
	],
	alert: [
		['circle', { cx: '12', cy: '12', r: '10' }],
		['line', {}],
		['line', {}]
	],
	shield: [
		[
			'path',
			{
				d: 'M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z'
			}
		]
	],
	cube: [
		[
			'path',
			{
				d: 'M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z'
			}
		],
		['path', { d: 'm3.3 7 8.7 5 8.7-5' }],
		['path', { d: 'M12 22V12' }]
	],
	terminal: [
		['path', { d: 'M12 19h8' }],
		['path', { d: 'm4 17 6-6-6-6' }]
	],
	pin: [
		['path', { d: 'M12 17v5' }],
		[
			'path',
			{
				d: 'M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H8a2 2 0 0 0 0 4 1 1 0 0 1 1 1z'
			}
		]
	],
	book: [
		['path', { d: 'M12 5v16' }],
		[
			'path',
			{
				d: 'M20.001 19A2 2 0 0022 17V5a2 2 0 00-1.999-2L16 3.002A5 5 0 0012 5a5 5 0 00-4-2H4a2 2 0 00-2 2v12a2 2 0 001.999 2H8a5 5 0 014 2 5 5 0 014-2z'
			}
		]
	],
	share: [
		['path', { d: 'M12 2v13' }],
		['path', { d: 'm16 6-4-4-4 4' }],
		['path', { d: 'M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8' }]
	],
	phone: [
		[
			'path',
			{
				d: 'M10.1 13.9a14 14 0 0 0 3.732 2.668 1 1 0 0 0 1.213-.303l.355-.465A2 2 0 0 1 17 15h3a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2 18 18 0 0 1-12.728-5.272'
			}
		],
		['path', { d: 'M22 2 2 22' }],
		[
			'path',
			{
				d: 'M4.76 13.582A18 18 0 0 1 2 4a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2v3a2 2 0 0 1-.8 1.6l-.468.351a1 1 0 0 0-.292 1.233 14 14 0 0 0 .244.473'
			}
		]
	],
	info: [
		['circle', { cx: '12', cy: '12', r: '10' }],
		['path', { d: 'M12 16v-4' }],
		['path', { d: 'M12 8h.01' }]
	],
	camera: [
		[
			'path',
			{
				d: 'M13.997 4a2 2 0 0 1 1.76 1.05l.486.9A2 2 0 0 0 18.003 7H20a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2h1.997a2 2 0 0 0 1.759-1.048l.489-.904A2 2 0 0 1 10.004 4z'
			}
		],
		['circle', { cx: '12', cy: '13', r: '3' }]
	],
	chevL: [['path', { d: 'm15 18-6-6 6-6' }]],
	minus: [['path', { d: 'M5 12h14' }]],
	expand: [
		['path', { d: 'M15 3h6v6' }],
		['path', { d: 'm21 3-7 7' }],
		['path', { d: 'm3 21 7-7' }],
		['path', { d: 'M9 21H3v-6' }]
	],
	brain: [
		['path', { d: 'M12 18V5' }],
		['path', { d: 'M15 13a4.17 4.17 0 01-3-4 4.17 4.17 0 01-3 4' }],
		['path', { d: 'M17.707 6.294A3 3 0 1012 5a3 3 0 10-5.707 1.294' }],
		['path', { d: 'M17.996 5.125a4 4 0 012.526 5.77' }],
		['path', { d: 'M18 18a4 4 0 002-7.465' }],
		['path', { d: 'M19.967 17.482a4 4 0 11-7.967.517 4 4 0 11-7.967-.517' }],
		['path', { d: 'M6 18a4 4 0 01-2-7.465' }],
		['path', { d: 'M6.004 5.125a4 4 0 00-2.526 5.77' }]
	],
	menu: [
		['path', { d: 'M4 5h16' }],
		['path', { d: 'M4 12h16' }],
		['path', { d: 'M4 19h16' }]
	],
	help: [
		['circle', { cx: '12', cy: '12', r: '10' }],
		['path', { d: 'M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3' }],
		['path', { d: 'M12 17h.01' }]
	],
	chart: [
		['path', { d: 'M3 3v16a2 2 0 0 0 2 2h16' }],
		['path', { d: 'M18 17V9' }],
		['path', { d: 'M13 17V5' }],
		['path', { d: 'M8 17v-3' }]
	],
	lock: [
		['rect', { width: '18', height: '11', x: '3', y: '11', rx: '2', ry: '2' }],
		['path', { d: 'M7 11V7a5 5 0 0 1 10 0v4' }]
	],
	sprout: [
		['path', { d: 'M7 20h10' }],
		['path', { d: 'M10 20c5.5-2.5.8-6.4 3-10' }],
		[
			'path',
			{
				d: 'M9.5 9.4c1.1.8 1.8 2.2 2.3 3.7-2 .4-3.5.4-4.8-.3-1.2-.6-2.3-1.9-3-4.2 2.8-.5 4.4 0 5.5.8z'
			}
		],
		[
			'path',
			{ d: 'M14.1 6a7 7 0 0 0-1.1 4c1.9-.1 3.3-.6 4.3-1.4 1-1 1.6-2.3 1.7-4.6-2.7.1-4 1-4.9 2z' }
		]
	]
} satisfies Record<string, IconPart[]>;

export type IconName = keyof typeof ICONS;
