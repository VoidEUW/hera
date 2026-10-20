import { t } from '$lib/i18n';

/** This machine's own zone, offered first — it is right almost every time, and typing
 * `Europe/Berlin` from memory is not something anybody should have to do. */
export const detectedZone = (() => {
	try {
		return Intl.DateTimeFormat().resolvedOptions().timeZone ?? '';
	} catch {
		return '';
	}
})();

/** Every zone the browser knows, so the list is the real one rather than a table here that
 * would go stale the next time a country changed its mind. Older browsers without
 * `supportedValuesOf` get UTC plus the detected zone, which covers the useful case. */
export const zoneChoices = (() => {
	const all =
		typeof Intl.supportedValuesOf === 'function'
			? Intl.supportedValuesOf('timeZone')
			: [detectedZone].filter(Boolean);
	return [
		{ value: '', label: t.profileMenu.timezoneUtc },
		...(detectedZone
			? [{ value: detectedZone, label: t.profileMenu.timezoneDetect(detectedZone) }]
			: []),
		...all.filter((zone) => zone !== detectedZone).map((zone) => ({ value: zone, label: zone }))
	];
})();
