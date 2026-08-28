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
		hint: 'Enter to send, Shift+Enter for a new line',
		model: 'Model',
		profile: 'Profile',
		noModel: 'No model',
		skillCount: (n: number) => `${n} ${n === 1 ? 'skill' : 'skills'}`,
		serverCount: (n: number) => `${n} ${n === 1 ? 'server' : 'servers'}`
	},

	select: {
		none: '—',
		empty: 'Nothing to choose from.'
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
		noProjects: 'No projects yet.',
		chatOptions: 'Chat options',
		projectOptions: 'Project options',
		rename: 'Rename',
		delete: 'Delete',
		deleteAsk: 'Delete this chat?',
		cancel: 'Cancel',
		open: 'Open',
		archive: 'Archive',
		moveTo: 'Move to…',
		noProject: 'No project',
		// "Remove" rather than "Delete": the chats inside are kept and come back as loose ones,
		// and a word that promises otherwise is the wrong word on a confirmation.
		removeProject: 'Remove project',
		removeProjectAsk: 'Remove this project? Its chats are kept.',
		projectNamePlaceholder: 'Project name'
	},

	project: {
		instructions: 'Instructions',
		instructionsHint:
			'What we are working on. If a sentence would still be true in a project about something else, it belongs in her mind instead.',
		skills: 'Pinned skills',
		skillsHint: 'Every chat in this project carries these, ahead of the profile’s.',
		chooseSkills: 'Choose skills',
		defaultProfile: 'Default profile',
		defaultProfileHint: 'Who a new chat here starts as.',
		noDefaultProfile: 'No default',
		defaultAgent: 'Default agent',
		defaultAgentSoon: 'Agents arrive in v0.3.',
		chats: 'Chats',
		noChats: 'No chats in this project yet.',
		save: 'Save',
		saved: 'Saved',
		notFound: 'There is no such project.',
		colour: 'Colour'
	},

	activity: {
		skill: 'skill',
		read: 'read',
		ran: 'ran',
		called: 'called',
		running: 'running…',
		thoughtFor: 'thought',
		show: 'Show',
		hide: 'Hide',
		pinned: 'skill · always active',
		slash: 'skill · you asked for it',
		retrieved: 'skill · matched this turn',
		lines: (n: number) => `${n} lines — scroll for the rest`,
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
		title: (action: string) => `Run ${action}?`,
		titleFrom: (action: string, server: string) => `Run ${action} from ${server}?`,
		allowOnce: 'Allow once',
		alwaysAllow: 'Always allow',
		deny: 'Deny',
		allowedOnce: 'Allowed once',
		alwaysAllowed: 'Always allowed — a rule was written',
		denied: 'Denied'
	},

	question: {
		asked: 'asked you',
		nothing: 'She asked something, and it arrived empty.',
		placeholder: 'Answer…',
		noReply: 'You answered with nothing.',
		send: 'Reply'
	},

	message: {
		copy: 'Copy',
		copied: 'Copied',
		edit: 'Edit',
		retry: 'Try again',
		cancel: 'Cancel',
		// Not "Send": the composer's button already says that, and this one does something
		// else -- it replaces a question that was already asked.
		saveAndSend: 'Ask again',
		editNote: 'Her answer to the old wording goes.'
	},

	turn: {
		cancelled: 'Interrupted',
		failed: 'This turn failed',
		max_iterations: 'She stopped after using tools too many times',
		awaiting_permission: 'Waiting for you',
		awaiting_answer: 'Waiting for your answer'
	},

	emotions: {
		blurb:
			'The stances she can show beside an answer. What you write here is what she reads before choosing one, and the tone is the colour the card is drawn in. She may still invent a kind when none of these is honest.',
		kind: 'agree',
		when: 'When is this one honest?',
		tone: 'Tone',
		tones: { warm: 'Warm', cool: 'Cool', sharp: 'Careful', soft: 'Quiet' },
		add: 'Add a stance',
		save: 'Add',
		cancel: 'Cancel',
		remove: 'Remove',
		reset: 'Reset to hers'
	},

	skills: {
		title: 'Skills for this chat',
		blurb:
			'Switched on for every message here, whatever retrieval decides. She still finds others on her own.',
		search: 'Search skills',
		close: 'Close',
		nothing: 'No description — retrieval can never find this one.',
		pick: 'Choose skills'
	},

	settings: {
		title: 'Settings',
		subtitle: 'How she works: what she runs on, what she knows, what she may do.',
		close: 'Close',
		search: 'Search settings',
		noMatch: 'Nothing here matches that.',
		models: 'Models',
		mind: 'Mind',
		skills: 'Skills',
		servers: 'Servers',
		permissions: 'Permissions',
		emotions: 'Emotions',
		dreaming: 'Dreaming',
		soon: 'v0.2',
		dreamingSoon:
			'Dreaming and experience training arrive in v0.2, together with memory. She will propose changes to her own evolvable mind regions, and nothing is written without you accepting it.',
		appearance: 'Appearance',
		system: 'System',
		light: 'Light',
		dark: 'Dark',
		profiles: 'Profiles',
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
		by: (author: string) => `by ${author}`,
		verified: 'Verified',
		modified: 'Changed since you trusted it',
		trustNote:
			'A verified mark comes from trusted.json in your Hera directory: a skill id and the SHA-256 you accepted. Nothing is verified until it is listed there.',
		connected: 'Connected',
		disconnected: 'Not running',
		lastUsed: 'Last used',
		never: 'Never used',
		usedTimes: (n: number) => `Used ${n} ${n === 1 ? 'time' : 'times'}`,
		addSkill: 'Add a skill',
		skillId: 'note-taking',
		skillIdRule: 'Lowercase letters, digits and hyphens. It becomes the folder and the /command.',
		skillDescription: 'Use when… — the line retrieval matches on',
		create: 'Create',
		cancel: 'Cancel',
		version: (v: string) => `v${v.replace(/^v/, '')}`
	},

	models: {
		blurb:
			'Where she runs. Any OpenAI-compatible endpoint — LM Studio, llama.cpp, vLLM, Ollama, or a hosted API.',
		active: 'Active',
		activate: 'Use this one',
		add: 'Add an endpoint',
		name: 'Name',
		baseUrl: 'Base URL',
		model: 'Model',
		embeddingModel: 'Embedding model',
		embeddingHint: 'Optional. Empty means retrieval falls back to keyword overlap.',
		apiKey: 'API key',
		keyStored: 'A key is stored. Leave this empty to keep it.',
		keyBlank: 'No key — the usual case for a local server.',
		test: 'Test',
		testing: 'Asking…',
		reachable: (n: number) => `Reachable — ${n} ${n === 1 ? 'model' : 'models'}`,
		pick: 'Use',
		unreachable: 'Could not reach it',
		remove: 'Remove',
		none: 'No endpoint registered yet. Add one and she has somewhere to think.',
		saved: 'Saved',
		nameRule: 'Lowercase letters, digits, - and _'
	},

	profileMenu: {
		open: 'You and this machine',
		appearance: 'Appearance',
		profiles: 'Answering as',
		makeDefault: 'Make default',
		language: 'Language',
		languageOnly: 'English for now; the interface is ready for more.',
		about: 'About',
		checking: 'Asking her where she lives…',
		version: (v: string) => `Hera ${v}`,
		dataIn: 'Your data is in',
		settings: 'Settings'
	},

	attach: {
		add: 'Attach a file or a picture',
		remove: 'Remove',
		tooBig: (name: string) => `${name} is too large to attach — 2 MB is the limit for text.`,
		imageTooBig: (name: string) =>
			`${name} is too large to attach — 12 MB is the limit for a picture.`,
		notText: (name: string) =>
			`${name} does not look like text, so there is nothing to send. PDFs are not readable yet.`,
		notAnImage: (name: string, type: string) =>
			`${name} is ${type || 'a kind of image'}, which she cannot be shown — PNG, JPEG, WebP and GIF work.`,
		image: 'image',
		note: 'Attached files are sent as part of your message.'
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
