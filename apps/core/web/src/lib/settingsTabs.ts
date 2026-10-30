/**
 * Which screens Settings has, grouped by what kind of thing a setting is — shared by the Settings
 * dialog, which draws them as its sidebar, and the command palette, which lists them as places
 * to jump to (#112). One list, so a screen added here appears in both.
 */
import { t } from '$lib/i18n';
import type { IconName } from '$lib/icons';

export type Tab =
	| 'account'
	| 'general'
	| 'hotkeys'
	| 'usage'
	| 'models'
	| 'skills'
	| 'servers'
	| 'permissions'
	| 'memory'
	| 'mind'
	| 'dreaming'
	| 'users'
	| 'instance'
	| 'mail';

export interface TabEntry {
	id: Tab;
	label: string;
	blurb: string;
	icon: IconName;
	/** Listed and disabled: a feature you can see coming is a promise. */
	soon?: boolean;
	/** The instance's, not a person's (ADR 28): only an admin sees the screen at all. */
	admin?: boolean;
}

export const GROUPS: Array<{ label: string; entries: TabEntry[] }> = [
	{
		label: t.settings.groupApp,
		entries: [
			{ id: 'account', label: t.settings.account, blurb: t.settings.blurbAccount, icon: 'user' },
			{ id: 'general', label: t.settings.general, blurb: t.settings.blurbGeneral, icon: 'sliders' },
			{
				id: 'hotkeys',
				label: t.settings.hotkeys,
				blurb: t.settings.blurbHotkeys,
				icon: 'keyboard'
			},
			{ id: 'usage', label: t.settings.usage, blurb: t.settings.blurbUsage, icon: 'chart' }
		]
	},
	{
		label: t.settings.groupHera,
		entries: [
			{ id: 'mind', label: t.settings.mind, blurb: t.settings.blurbMind, icon: 'brain' },
			{ id: 'memory', label: t.settings.memory, blurb: t.settings.blurbMemory, icon: 'clock' },
			{
				id: 'models',
				label: t.settings.models,
				blurb: t.settings.blurbModels,
				icon: 'cube',
				admin: true
			},
			{
				id: 'dreaming',
				label: t.settings.dreaming,
				blurb: t.settings.blurbDreaming,
				icon: 'moon',
				soon: true
			}
		]
	},
	{
		label: t.settings.groupAdjust,
		entries: [
			{
				id: 'skills',
				label: t.settings.skills,
				blurb: t.settings.blurbSkills,
				icon: 'spark',
				admin: true
			},
			{
				id: 'servers',
				label: t.settings.servers,
				blurb: t.settings.blurbServers,
				icon: 'plug',
				admin: true
			},
			{
				id: 'permissions',
				label: t.settings.permissions,
				blurb: t.settings.blurbPermissions,
				icon: 'shield'
			}
		]
	},
	{
		// The instance and the people on it (ADR 27). Every entry is an admin's, so the whole group
		// is absent for anybody else.
		label: t.settings.groupAdmin,
		entries: [
			{
				id: 'users',
				label: t.settings.users,
				blurb: t.settings.blurbUsers,
				icon: 'users',
				admin: true
			},
			{
				id: 'instance',
				label: t.settings.instance,
				blurb: t.settings.blurbInstance,
				icon: 'globe',
				admin: true
			},
			{
				id: 'mail',
				label: t.settings.mail,
				blurb: t.settings.blurbMail,
				icon: 'mail',
				admin: true
			}
		]
	}
];

export const ENTRIES: TabEntry[] = GROUPS.flatMap((group) => group.entries);

/** The groups somebody sees: everything for an admin, and without the instance's screens for
 * anybody else — a screen whose every control answers 403 is a door painted on a wall. */
export function groupsFor(admin: boolean): typeof GROUPS {
	return GROUPS.map((group) => ({
		...group,
		entries: group.entries.filter((entry) => admin || !entry.admin)
	})).filter((group) => group.entries.length > 0);
}

export function entriesFor(admin: boolean): TabEntry[] {
	return groupsFor(admin).flatMap((group) => group.entries);
}
