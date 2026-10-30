/**
 * Copying text, wherever Hera is opened.
 *
 * `navigator.clipboard` exists only in a secure context — https, or `localhost` — and a Hera
 * opened at `http://192.168.1.20:8756` on a LAN is neither, so a copy button there did nothing
 * at all. The old `execCommand('copy')` path still works over plain http and is the fallback.
 *
 * The text may be a promise, for a button that first has to ask the server what to copy (a new
 * invitation link). Safari only lets a page write to the clipboard inside the click that asked,
 * and an awaited request ends that; a `ClipboardItem` built from the promise is how it allows
 * the write to finish later. The fallback cannot wait, so it gets the text once it is there.
 */

export async function copyText(text: string | Promise<string>): Promise<boolean> {
	if (window.isSecureContext && navigator.clipboard) {
		try {
			if (typeof text !== 'string' && typeof ClipboardItem !== 'undefined') {
				const blob = text.then((value) => new Blob([value], { type: 'text/plain' }));
				await navigator.clipboard.write([new ClipboardItem({ 'text/plain': blob })]);
			} else {
				await navigator.clipboard.writeText(await text);
			}
			return true;
		} catch {
			// Refused — a browser that wants the click to be more recent. The fallback may manage.
		}
	}
	return fallback(await text);
}

function fallback(text: string): boolean {
	// Built in script rather than drawn: it lives for one call and nobody ever sees it.
	const scratch = document.createElement('textarea');
	scratch.value = text;
	scratch.setAttribute('readonly', '');
	scratch.style.position = 'fixed';
	scratch.style.opacity = '0';
	document.body.append(scratch);
	scratch.select();
	try {
		return document.execCommand('copy');
	} catch {
		return false;
	} finally {
		scratch.remove();
	}
}
