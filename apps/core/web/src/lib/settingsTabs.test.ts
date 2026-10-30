import { describe, expect, it } from 'vitest';
import { entriesFor, groupsFor } from './settingsTabs';

describe('which screens somebody sees', () => {
	it('gives an admin every screen', () => {
		expect(entriesFor(true).map((entry) => entry.id)).toContain('servers');
	});

	it('leaves the instance’s screens out for everybody else', () => {
		const ids = entriesFor(false).map((entry) => entry.id);
		for (const instance of ['models', 'skills', 'servers']) expect(ids).not.toContain(instance);
		for (const theirs of ['account', 'mind', 'memory', 'permissions'])
			expect(ids).toContain(theirs);
	});

	it('draws the Admin group for an admin only, since every screen in it is theirs', () => {
		const admin = groupsFor(true).find((group) => group.label === 'Admin');
		expect(admin?.entries.map((entry) => entry.id)).toEqual(['users', 'instance', 'mail']);
		expect(groupsFor(false).map((group) => group.label)).not.toContain('Admin');
	});
});
