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
		openMenu: 'Open menu',
		closeMenu: 'Close menu',
		title: 'Chats and projects',
		noChats: 'No chats yet.',
		noProjects: 'No projects yet.',
		chatOptions: 'Chat options',
		projectOptions: 'Project options',
		rename: 'Rename',
		delete: 'Delete',
		deleteAsk: 'Delete this chat?',
		/** What else goes with it. A chat owns what she published in it, and *a chat is a thing
		 * you throw away* has to be reconciled with *the page I made last week* by a sentence
		 * rather than by a surprise (ADR 13). */
		deleteTakes: (n: number) =>
			n === 1 ? 'The artifact in it goes too.' : `The ${n} artifacts in it go too.`,
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
		didThings: (n: number) => (n === 1 ? '1 thing she did' : `${n} things she did`),
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
		send: 'Reply',
		/** What sort of question it is, from `hera_mcp.ASK_KINDS` (ADR 17). Three words in the
		 * *person's* register rather than the model's: `blocked` is what the tool calls it, and
		 * *she cannot go on* is what it means to whoever is being asked. A kind not in here —
		 * a turn persisted before the set was closed carries a stance word — draws nothing. */
		kinds: {
			unsure: 'she is unsure',
			blocked: 'she cannot go on',
			choice: 'she needs you to choose'
		} as Record<string, string>
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
		max_iterations: 'She ran out of tool calls and answered with what she had',
		awaiting_permission: 'Waiting for you',
		awaiting_answer: 'Waiting for your answer'
	},

	memory: {
		blurb:
			'What she has written down about you. Every one of these that is switched on is in her prompt, whole — there is nothing to search and nothing that can quietly fail to arrive. That takes space, so the space is here to see.',
		/** The number that matters, said first. *Left* is what a person is steering by; *used of*
		 * is the detail underneath it. */
		left: (n: number) => `${n.toLocaleString()} tokens left`,
		used: (used: number, limit: number) =>
			`${used.toLocaleString()} of ${limit.toLocaleString()} used`,
		spaceLabel: 'Space her memories take',
		carried: (n: number) => `${n} ${n === 1 ? 'memory' : 'memories'}`,
		off: (n: number) => `${n} switched off`,
		tokens: (n: number) => `${n} tokens`,
		/** On the switch. Not "Enabled": what it does is decide whether she carries this one, and
		 * the whole point of the control is that switching it off is not throwing it away. */
		on: 'In use',
		offOne: 'Kept, not used',
		useIt: (key: string) => `Use ${key}`,
		hereOnly: 'this chat only',
		hers: 'she wrote it',
		yours: 'you wrote it',
		because: (why: string) => `because ${why}`,
		edit: 'Edit',
		save: 'Save',
		// The three fields a person may change. The key is not one of them: the filename is the
		// identity, so renaming would make a different memory with the same words in it.
		description: 'Summary',
		text: 'What she knows',
		why: 'Why it was kept',
		whyHint: 'Optional',
		editNote:
			'Only what she knows goes into her prompt. The summary and the reason are for this screen.',
		delete: 'Delete',
		// The only delete in the system that actually removes a memory. Her own `forget` keeps
		// the file, so this sentence has to be the one that says the difference out loud.
		deleteAsk: 'Delete this memory? It is not kept anywhere else.',
		cancel: 'Cancel',
		export: 'Export MEMORY.md',
		none: 'Nothing yet. She writes these as she learns things worth keeping, and you can drop a markdown file into your memories directory yourself.'
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
		memory: 'Memory',
		skills: 'Skills',
		servers: 'Servers',
		permissions: 'Permissions',
		dreaming: 'Dreaming',
		soon: 'v0.3',
		dreamingSoon:
			'Dreaming and experience training arrive in v0.3. She will propose changes to her own evolvable mind regions, and nothing is written without you accepting it. Memory comes first, in v0.2 — she has to have something to reflect on.',
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
		timeout: 'Silence before giving up',
		timeoutHint:
			'Seconds this endpoint may go quiet — loading the model, or working through a long ' +
			'prompt. Not a limit on how long an answer may take. Raise it if a turn ends with ' +
			'“did not answer in time”.',
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
		timezone: 'Time zone',
		timezoneHint: 'What she is told the date and time are. She is always told UTC as well.',
		timezoneUtc: 'UTC only',
		timezoneDetect: (zone: string) => `Use this machine’s (${zone})`,
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

	artifact: {
		/** The card's button. Not "View": what happens is a panel opening beside the
		 * conversation, and it is the same verb whether the thing is a page or a document. */
		open: 'Open',
		/** The same button under something already drawn in the flow, where *Open* would read as
		 * an offer to show what is plainly already there. */
		openFull: 'Full size',
		download: 'Download',
		/** The card's save control is a glyph, so its accessible name says *which* file — a turn
		 * that published four of them otherwise offers four identical buttons. */
		downloadOne: (name: string) => `Download ${name}`,
		close: 'Close',
		panel: 'Artifacts',
		files: 'Everything published here',
		none: 'Nothing chosen yet.',
		loading: 'Fetching it…',
		count: (n: number) => (n === 1 ? '1 artifact' : `${n} artifacts`),
		/** A `.mmd` file is still a file she made, and its source is worth reading. Showing
		 * nothing at all is what makes a renderer this build does not have look like an artifact
		 * that came out broken. */
		noMermaid: 'Mermaid diagrams are not drawn in this version — the source is below.'
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
