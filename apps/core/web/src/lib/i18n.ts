/**
 * Every user-visible string, in one place.
 *
 * English, through a seam, so a German locale can be added without touching a component. The
 * seam is the point — CLAUDE.md requires it, and a component with a literal in it is a
 * component that has to be reopened for every language.
 *
 * Sentence case. Active voice. A control says what happens: **Send**, not *Submit*. An action
 * keeps its name all the way through — the button that says "Always allow" produces a
 * confirmation that says "Always allowed". Failures explain what happened and what to do, and
 * they do not apologise.
 */

export const t = {
	appName: 'Hera',

	greeting: {
		morning: 'Good morning',
		afternoon: 'Good afternoon',
		evening: 'Good evening',
		night: 'Still up'
	},

	composer: {
		placeholder: 'What are we doing today?',
		reply: 'Reply…',
		send: 'Send',
		stop: 'Stop',
		hint: 'Enter to send, Shift+Enter for a new line'
	},

	rail: {
		newChat: 'New chat',
		search: 'Search',
		projects: 'Projects',
		newProject: 'New project',
		chats: 'Chats',
		settings: 'Settings',
		collapse: 'Collapse the sidebar',
		expand: 'Expand the sidebar',
		noChats: 'No chats yet.',
		noProjects: 'No projects yet.'
	},

	activity: {
		used: 'used',
		read: 'read',
		ran: 'ran',
		running: 'running…',
		thoughtFor: 'thought',
		show: 'Show',
		hide: 'Hide',
		pinned: 'skill · always active',
		slash: 'skill · you asked for it',
		retrieved: 'skill · matched this turn',
		unknown: 'Something this version does not know how to show'
	},

	failure: {
		denied: 'not allowed',
		unknown_tool: 'no such tool',
		unavailable: 'is not running',
		timeout: 'gave up waiting',
		tool_error: 'the tool said no'
	},

	permission: {
		title: (tool: string) => `Run ${tool}?`,
		allowOnce: 'Allow once',
		alwaysAllow: 'Always allow',
		deny: 'Deny',
		allowedOnce: 'Allowed once',
		alwaysAllowed: 'Always allowed — a rule was written',
		denied: 'Denied'
	},

	turn: {
		cancelled: 'Interrupted',
		failed: 'This turn failed',
		max_iterations: 'She stopped after using tools too many times',
		awaiting_permission: 'Waiting for you'
	},

	settings: {
		title: 'Settings',
		close: 'Close',
		general: 'General',
		appearance: 'Appearance',
		system: 'System',
		light: 'Light',
		dark: 'Dark',
		mind: 'Mind',
		profiles: 'Profiles',
		skills: 'Skills',
		servers: 'Servers',
		permissions: 'Permissions',
		save: 'Save',
		saved: 'Saved',
		ownerFixed: 'Only you may change this',
		evolvable: 'She may propose changes to this',
		generation: (n: number) => `${n} ${n === 1 ? 'revision' : 'revisions'}`,
		noSkills:
			'A skill is a folder with a SKILL.md in it — a name, a description of when to use it, and instructions. Put one in your skills directory and it appears here.',
		noServers:
			'Tools come from MCP servers listed in mcp.json. Add one and it appears here with its tools.',
		noPermissions: 'Nothing has been decided yet. Rules appear here as you answer cards.',
		broken: 'Could not be read',
		connected: 'Connected',
		disconnected: 'Not running',
		lastUsed: 'Last used',
		never: 'Never used',
		usedTimes: (n: number) => `Used ${n} ${n === 1 ? 'time' : 'times'}`
	},

	empty: {
		title: 'Nothing here yet',
		chat: 'Say something to start.'
	},

	error: {
		load: 'Could not load that',
		send: 'The message did not go through',
		retry: 'Try again'
	}
} as const;

export function greetingFor(date: Date = new Date()): string {
	const hour = date.getHours();
	if (hour < 5) return t.greeting.night;
	if (hour < 12) return t.greeting.morning;
	if (hour < 18) return t.greeting.afternoon;
	return t.greeting.evening;
}

/** "12 ms", "1.4 s" — a duration a person reads rather than a number they convert. */
export function duration(ms: number): string {
	if (ms < 1000) return `${ms} ms`;
	return `${(ms / 1000).toFixed(1)} s`;
}
