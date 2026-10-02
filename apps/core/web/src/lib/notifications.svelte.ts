/**
 * Tell me when a turn finishes in a tab I am not looking at.
 *
 * One preference, kept in localStorage beside the theme and read by nothing on the server: it
 * is about this browser, and a long turn finishing in a background tab is silent without it.
 * Turning it on is also what asks the browser for permission, because asking on page load —
 * before anyone knows what for — is how a prompt gets reflexively denied.
 */

const KEY = 'hera:notify';

export type Permission = NotificationPermission | 'unsupported';

function permission(): Permission {
	return typeof Notification === 'undefined' ? 'unsupported' : Notification.permission;
}

class Notifications {
	/** Whether the person asked for this. Not whether it can happen: that is `permission`. */
	enabled = $state(false);
	permission = $state<Permission>('default');

	load() {
		this.enabled = localStorage.getItem(KEY) === '1';
		this.permission = permission();
	}

	/** Turn it on or off. Turning on asks for permission if it has not been decided; a refusal
	 * leaves the preference off, so the switch never says *on* about something that cannot
	 * happen. */
	async set(enabled: boolean) {
		if (enabled && this.permission === 'default') {
			this.permission = (await Notification.requestPermission()) as Permission;
		}
		this.enabled = enabled && this.permission === 'granted';
		localStorage.setItem(KEY, this.enabled ? '1' : '0');
	}

	/** A turn has finished. Says so only if asked to, allowed to, and nobody is looking. */
	turnFinished(title: string) {
		if (!this.enabled || this.permission !== 'granted' || !document.hidden) return;
		new Notification(title);
	}
}

export const notifications = new Notifications();
