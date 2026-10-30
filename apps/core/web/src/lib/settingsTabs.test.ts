import { describe, expect, it } from 'vitest';
import { entriesFor } from './settingsTabs';

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
});
