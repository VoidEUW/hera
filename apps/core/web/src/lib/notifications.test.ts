import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

class FakeNotification {
	static permission: NotificationPermission = 'default';
	static requestPermission = vi.fn(async () => FakeNotification.permission);
	static shown: string[] = [];
	constructor(title: string) {
		FakeNotification.shown.push(title);
	}
}

async function fresh() {
	vi.resetModules();
	const { notifications } = await import('./notifications.svelte');
	return notifications;
}

describe('notifications', () => {
	beforeEach(() => {
		const store = new Map<string, string>();
		vi.stubGlobal('localStorage', {
			getItem: (key: string) => store.get(key) ?? null,
			setItem: (key: string, value: string) => void store.set(key, value)
		});
		FakeNotification.permission = 'default';
		FakeNotification.shown = [];
		FakeNotification.requestPermission.mockClear();
		vi.stubGlobal('Notification', FakeNotification);
		vi.stubGlobal('document', { hidden: true });
	});

	afterEach(() => vi.unstubAllGlobals());

	it('asks for permission when turned on and remembers the choice', async () => {
		const notifications = await fresh();
		notifications.load();
		FakeNotification.requestPermission.mockImplementation(async () => {
			FakeNotification.permission = 'granted';
			return 'granted';
		});
		await notifications.set(true);
		expect(notifications.enabled).toBe(true);
		expect(localStorage.getItem('hera:notify')).toBe('1');
	});

	it('stays off when the browser refuses', async () => {
		const notifications = await fresh();
		notifications.load();
		FakeNotification.requestPermission.mockImplementation(async () => 'denied');
		await notifications.set(true);
		expect(notifications.enabled).toBe(false);
		expect(localStorage.getItem('hera:notify')).toBe('0');
	});

	it('only notifies while the tab is hidden', async () => {
		FakeNotification.permission = 'granted';
		localStorage.setItem('hera:notify', '1');
		const notifications = await fresh();
		notifications.load();
		notifications.turnFinished('done');
		expect(FakeNotification.shown).toEqual(['done']);
		vi.stubGlobal('document', { hidden: false });
		notifications.turnFinished('again');
		expect(FakeNotification.shown).toEqual(['done']);
	});
});
