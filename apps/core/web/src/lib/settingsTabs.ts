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
	| 'models'
	| 'skills'
	| 'servers'
	| 'permissions'
	| 'memory'
	| 'mind'
	| 'dreaming';

export interface TabEntry {
	id: Tab;
	label: string;
	blurb: string;
	icon: IconName;
	/** Listed and disabled: a feature you can see coming is a promise. */
	soon?: boolean;
}

export const GROUPS: Array<{ label: string; entries: TabEntry[] }> = [
	{
		label: t.settings.groupApp,
		entries: [
			{ id: 'account', label: t.settings.account, blurb: t.settings.blurbAccount, icon: 'user' },
			{ id: 'general', label: t.settings.general, blurb: t.settings.blurbGeneral, icon: 'sliders' },
			{ id: 'hotkeys', label: t.settings.hotkeys, blurb: t.settings.blurbHotkeys, icon: 'keyboard' }
		]
	},
	{
		label: t.settings.groupHera,
		entries: [
			{ id: 'mind', label: t.settings.mind, blurb: t.settings.blurbMind, icon: 'brain' },
			{ id: 'memory', label: t.settings.memory, blurb: t.settings.blurbMemory, icon: 'clock' },
			{ id: 'models', label: t.settings.models, blurb: t.settings.blurbModels, icon: 'cube' },
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
			{ id: 'skills', label: t.settings.skills, blurb: t.settings.blurbSkills, icon: 'spark' },
			{ id: 'servers', label: t.settings.servers, blurb: t.settings.blurbServers, icon: 'plug' },
			{
				id: 'permissions',
				label: t.settings.permissions,
				blurb: t.settings.blurbPermissions,
				icon: 'shield'
			}
		]
	}
];

export const ENTRIES: TabEntry[] = GROUPS.flatMap((group) => group.entries);
