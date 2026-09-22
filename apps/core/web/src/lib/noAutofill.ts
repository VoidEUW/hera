/**
 * Spread onto a text-like `<input>` that a password manager should leave alone.
 *
 * A settings screen with a name, a URL and a key field beside each other reads to a password
 * manager as a login form — 1Password offered to fill the provider's name from a saved identity,
 * and offered to save the API key as a new password, on a field that is neither. `autocomplete`
 * is the standard the browser itself honours; the four `data-*` flags are what the password
 * managers people actually run honour when a browser ignores it, one attribute per vendor since
 * none of them read another's.
 */
export const noAutofill = {
	autocomplete: 'off',
	'data-1p-ignore': 'true',
	'data-lpignore': 'true',
	'data-bwignore': 'true',
	'data-protonpass-ignore': 'true',
	'data-form-type': 'other'
} as const;
