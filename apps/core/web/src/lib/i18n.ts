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
		serverCount: (n: number) => `${n} ${n === 1 ? 'server' : 'servers'}`,
		/** A fixed vocabulary offered here, not one read from the server — there is no catalogue
		 * of valid values (ADR 18: Hera does not interpret a model's `options`). Changing it is
		 * global, the same reach as the model picker beside it: the value written to the active
		 * model's `options.reasoning_effort` applies to every chat from the next message on. */
		reasoning: 'Reasoning',
		thinking: 'Thinking',
		thinkingOn: 'She is thinking. Click to turn it off.',
		thinkingOff: 'Not thinking. Click to turn it on.',
		budgetTitle: 'Thinking budget, in tokens',
		budget: (tokens: number) =>
			`${tokens % 1024 === 0 ? `${tokens / 1024}k` : tokens.toLocaleString()} thinking`,
		tokens: 'tokens',
		effort: {
			// Only "absent from options" is a phrase. The values themselves are the endpoint's own
			// vocabulary -- `xhigh`, `minimal`, `none` are wire values a server matches on, so
			// translating one would change what is sent rather than what is read. They come from
			// `ModelOut.reasoning_efforts` and are drawn as they arrive.
			default: 'Default'
		},
		contextLabel: 'Context window',
		contextUsed: (used: number, limit: number) =>
			`${used.toLocaleString()} of ${limit.toLocaleString()} tokens`
	},

	select: {
		none: '—',
		empty: 'Nothing to choose from.'
	},

	rail: {
		search: 'Search chats',
		newChat: 'New chat',
		projects: 'Projects',
		newProject: 'New project',
		chats: 'Chats',
		settings: 'Settings',
		account: (name: string) => `${name} — Settings`,
		accountLabel: 'Account',
		resize: 'Resize the sidebar',
		openMenu: 'Open menu',
		closeMenu: 'Close menu',
		title: 'Chats and projects',
		noChats: 'No chats yet.',
		noProjects: 'No projects yet.',
		// Read out, never drawn: the placeholder they stand in for is bars of grey, which say
		// nothing to anyone who is not looking at it.
		loadingProjects: 'Loading projects…',
		loadingChats: 'Loading chats…',
		chatOptions: 'Chat options',
		projectOptions: 'Project options',
		rename: 'Rename',
		export: 'Export',
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
		loading: 'Loading the project…',
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
		did: 'did',
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
		heading: 'Permission',
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
		answered: 'Answered',
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
		editNote: 'Her answer to the old wording goes.',
		/** The speaker labels over a message: yours, and hers by name. */
		you: 'You',
		thinking: 'Thinking'
	},

	turn: {
		cancelled: 'Interrupted',
		failed: 'This turn failed',
		/** A turn that stopped without ever recording anything, and so has no reason to give.
		 * It is not a blank answer: the server closes the record on every path now, so reaching
		 * this means the turn was persisted before that, or by something that missed it. Said
		 * rather than left blank, because an empty bubble reads as *she had nothing to say* and
		 * invites a rewording of the question, which is the wrong response to a request the
		 * provider refused. */
		silent: 'This turn stopped without an answer',
		max_iterations: 'She ran out of tool calls and answered with what she had',
		awaiting_permission: 'Waiting for you',
		awaiting_answer: 'Waiting for your answer',
		/** How many tokens *this message* generated, in the corner nobody has to look at.
		 * `completion_tokens`, not the turn's total — the prompt side is mostly history carried
		 * forward, not something this message produced (issue #51 rules dollars out entirely — a
		 * deployment's pricing isn't Hera's to know either way). */
		tokens: (n: number) => `${n.toLocaleString()} tokens`
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
		// The disclosure under the one box: the two fields that never reach her prompt.
		more: 'Summary and reason',
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

	/** Settings → Usage (#111). */
	usage: {
		loading: 'Loading usage…',
		chart: (days: number) => `Tokens per day, the last ${days} days`,
		prompt: 'Read',
		completion: 'Written',
		/** The legend's longer names, for a person who wonders what "read" means here. */
		promptLong: 'Prompt tokens — what she read: the conversation, her mind, the tools',
		completionLong: 'Completion tokens — what she wrote back',
		day: 'Last 24 hours',
		week: 'Last 7 days',
		month: 'Last 30 days',
		tokens: (n: number) => `${n.toLocaleString()} tokens`,
		split: (prompt: number, completion: number) =>
			`${prompt.toLocaleString()} read · ${completion.toLocaleString()} written`,
		readout: (date: string, prompt: number, completion: number) =>
			`${date}: ${prompt.toLocaleString()} read, ${completion.toLocaleString()} written`,
		none: 'Nothing yet. Each answer she gives adds its tokens here, on the day it was given.',
		note: 'Counts are what the model endpoint reports for each answer. A server that reports nothing counts as nothing, and Hera does not estimate.',
		zone: (zone: string) => `Days in ${zone}`
	},

	skills: {
		title: 'Skills for this chat',
		blurb:
			'Switched on for every message here, whatever retrieval decides. She still finds others on her own.',
		search: 'Search skills',
		close: 'Close',
		nothing: 'No description — retrieval can never find this one.',
		pick: 'Choose skills',
		fromProfile: 'Pinned by the profile'
	},

	servers: {
		title: 'Servers she can reach',
		blurb:
			'Only connected servers count — one that failed to start changes nothing for the next message. Adding or removing one happens in Settings.',
		close: 'Close',
		toolSingular: 'tool',
		toolPlural: 'tools',
		none: 'No servers connected. Add one in Settings to give her more tools.',
		configure: 'Manage servers',
		heading: 'MCP servers',
		connected: 'connected',
		notConnected: 'not connected'
	},

	/** Settings → Servers: the boxes, their tools, and the add-a-server form (#108). */
	serverEditor: {
		newServer: 'New server',
		editServer: 'Edit server',
		hers: 'Hers — part of Hera, not in mcp.json',
		off: 'Off',
		stdio: 'Command',
		http: 'Web address',
		kindLabel: 'How it is reached',
		kindHelp: {
			stdio: 'Hera starts it as a program on this machine and talks to it directly.',
			http: 'It is already running somewhere, and Hera connects to its address.'
		},
		name: 'Name',
		nameHelp:
			'Letters, digits, “-” and “_”. It becomes the front of each tool: name__tool, and is what a permission rule is written against.',
		nameLocked: 'The name is what its tools and rules are called. To rename it, add a new one.',
		namePlaceholder: 'filesystem',
		command: 'Command',
		commandPlaceholder: 'npx',
		args: 'Arguments',
		argsHelp: 'One per line.',
		argsPlaceholder: '-y\n@modelcontextprotocol/server-filesystem\n/Users/me/notes',
		cwd: 'Working directory',
		cwdHelp: 'Optional. Where the program starts.',
		url: 'Address',
		urlPlaceholder: 'https://example.com/mcp',
		env: 'Environment',
		envHelp:
			'Set for the program only. Write ${NAME} to read a value from Hera’s own environment instead of saving it here.',
		headers: 'Headers',
		headersHelp:
			'Sent with every request. Write ${NAME} to read a value from Hera’s own environment instead of saving it here.',
		key: 'Name',
		value: 'Value',
		hiddenValue: 'Saved — type to replace',
		addRow: 'Add',
		removeRow: 'Remove this one',
		enabled: 'Enabled',
		enabledHelp: 'Off keeps it in the file without starting it.',
		save: 'Save server',
		create: 'Add server',
		cancel: 'Cancel',
		needName: 'Give it a name.',
		needCommand: 'Say which command to run.',
		needUrl: 'Say where it is.',
		edit: 'Edit this server',
		delete: 'Remove this server',
		deleteTitle: 'Remove this server?',
		deleteBody: (name: string) =>
			`${name} is taken out of mcp.json and stopped. Its tools go with it; rules that name them stay.`,
		deleteYes: 'Remove',
		deleteKeep: 'Keep it',
		toolsHeading: 'Tools',
		noTools: 'It has not offered any tools.',
		notConnected: 'Not connected, so there are no tools to list.',
		toolOn: (tool: string) => `She may use ${tool}`,
		deniedBy: (rule: string) => `Off by the rule ${rule}`,
		switchOff: 'Switched off in mcp.json. Edit it to turn it on.',
		toolsLoading: 'Reading its tools…'
	},

	/** Settings → Permissions: rules a person can make, change and remove (#109). */
	permissions: {
		rulesHeading: 'Rules',
		newRule: 'New rule',
		editRule: 'Edit rule',
		everything: 'Every tool',
		fromServer: (server: string) => `Every tool from ${server}`,
		oneTool: (server: string, tool: string) => `${tool} from ${server}`,
		matching: (pattern: string) => `Tools matching ${pattern}`,
		unnamed: 'Unnamed rule',
		decisions: {
			allow: { label: 'Allow', help: 'Runs without asking.' },
			ask: { label: 'Ask', help: 'Shows a card first, and you answer.' },
			deny: { label: 'Deny', help: 'Never runs, and she is told so.' }
		},
		decisionLabel: 'What happens',
		fallbackTitle: 'Everything else',
		fallbackHelp: 'What happens to a tool no rule covers — a new server, say.',
		sources: {
			default: 'Built in',
			card: 'From a card',
			profile: (name: string) => `Profile ${name}`
		},
		builtInNote: 'Built in rules can be changed but not deleted.',
		covers: (n: number) => (n === 1 ? 'Covers 1 tool' : `Covers ${n} tools`),
		coversNone: 'Covers none of her tools right now',
		name: 'Name',
		namePlaceholder: 'Reading files',
		nameHelp: 'Only for you. It does not change what the rule covers.',
		pattern: 'Applies to',
		patternPlaceholder: 'fs__read_file',
		patternHelp:
			'A tool is server__name. A * stands for anything: fs__* is every tool from fs, and * alone is every tool.',
		patternLocked:
			'The pattern is what makes it this rule. To cover something else, make a new rule.',
		previewSearching: 'Checking which tools that covers…',
		previewMatches: (n: number) =>
			n === 1 ? 'Covers 1 of her tools now:' : `Covers ${n} of her tools now:`,
		previewNone: 'None of her tools right now. It will apply when one that matches appears.',
		reason: 'Why',
		reasonHelp: 'Shown on the card, or with the refusal.',
		reasonPlaceholder: 'It only reads.',
		patternRequired: 'Say which tools it applies to.',
		save: 'Save rule',
		create: 'Add rule',
		cancel: 'Cancel',
		edit: 'Edit this rule',
		delete: 'Delete this rule',
		deleteTitle: 'Delete this rule?',
		deleteBody: (what: string) =>
			`${what} goes back to the next most specific rule, or to “everything else”.`,
		deleteYes: 'Delete',
		deleteKeep: 'Keep it'
	},
	/** The keymap (#112). The action and control names themselves live in `$lib/keys`, next to
	 * the chord they describe, so a binding and its words cannot drift apart. */
	hotkeys: {
		global: 'Everywhere',
		chat: 'In a chat',
		intro: 'They cannot be changed yet.',
		mirrors: (control: string) => `Same as: ${control}`,
		planned: 'Coming later'
	},
	/** The command palette, opened with the search chord. */
	palette: {
		label: 'Search and jump',
		placeholder: 'Search chats, projects and settings…',
		chatsPlaceholder: 'Search chats…',
		empty: 'Nothing matches that.',
		actions: 'Actions',
		chats: 'Chats',
		projects: 'Projects',
		settings: 'Settings',
		inProject: (name: string) => name
	},
	/** Hera's own find, in the top bar of a chat. */
	find: {
		label: 'Find in this chat',
		placeholder: 'Find in this chat',
		none: 'No matches',
		count: (at: number, of: number) => `${at} of ${of}`,
		next: 'Next match',
		previous: 'Previous match',
		close: 'Close find'
	},
	settings: {
		title: 'Settings',
		subtitle: 'How she works: what she runs on, what she knows, what she may do.',
		close: 'Close',
		search: 'Search settings',
		noMatch: 'Nothing here matches that.',
		// Read out, never drawn: a placeholder is bars of grey and says nothing to anybody who
		// is not looking at it.
		loading: 'Loading these settings…',
		loadingModels: 'Loading models…',
		loadingSkills: 'Loading skills…',
		loadingMemory: 'Loading memories…',
		account: 'Account',
		general: 'General',
		hotkeys: 'Hotkeys',
		usage: 'Usage',
		models: 'Models',
		mind: 'Mind',
		memory: 'Memory',
		skills: 'Skills',
		servers: 'Servers',
		permissions: 'Permissions',
		dreaming: 'Dreaming',
		groupApp: 'App',
		groupHera: 'Hera',
		groupAdjust: 'Adjust',
		// One line under each screen's heading: what it is for, not how to use it.
		blurbAccount: 'Who you are to Hera: a name, an email and a picture.',
		blurbGeneral: 'This browser and this machine: appearance, language, time zone, notifications.',
		blurbHotkeys: 'The keys that do what a button on screen already does.',
		blurbUsage: 'How many tokens her answers took, day by day.',
		blurbMind: 'The text that shapes how she thinks and speaks, one region at a time.',
		blurbMemory: 'What she knows about you, and how much room it takes.',
		blurbModels: 'Where she runs. Any OpenAI-compatible endpoint.',
		blurbDreaming: 'How she will reflect on herself — not built yet.',
		blurbSkills: 'Packages of instructions she can be given for a kind of task.',
		blurbServers:
			'The MCP servers she can reach, and the tools each one brings. Switch a tool off and she no longer has it.',
		blurbPermissions: 'What she may do without asking.',
		permissionsFallback: 'Anything not matched below:',
		toolCount: (n: number) => `${n} ${n === 1 ? 'tool' : 'tools'}`,
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
			'Tools come from MCP servers. Add one and it appears here with its tools — or list it in mcp.json yourself.',
		noPermissions: 'No rules yet. Make one, or answer “always” on a card.',
		broken: 'Could not be read',
		by: (author: string) => `by ${author}`,
		verified: 'Verified',
		modified: 'Changed since you trusted it',
		trustNote:
			'A verified mark comes from trusted.json in your Hera directory: a skill id and the SHA-256 you accepted. Nothing is verified until it is listed there.',
		connected: 'Connected',
		disconnected: 'Not running',
		lastUsed: 'Last used',
		useSkill: (id: string) => `Use ${id}`,
		editSkill: (id: string) => `Edit ${id}`,
		editSkillBlurb: 'The SKILL.md as it is on disk: frontmatter on top, the instructions below.',
		skillSource: 'SKILL.md',
		addSkill: 'Add a skill',
		newSkill: 'New skill',
		newSkillBlurb: 'Becomes a folder under ~/.hera/skills/, with this text as its SKILL.md.',
		skillId: 'note-taking',
		skillIdLabel: 'Id',
		skillIdRule: 'Lowercase letters, digits and hyphens. It becomes the folder and the /command.',
		create: 'Create',
		deleteSkill: 'Delete',
		deleteSure: (id: string) => `Delete ${id} and its folder? This cannot be undone.`,
		deleteKeep: 'Keep it',
		deleteYes: 'Delete skill',
		loadingSource: 'Loading…',
		readOnly: 'Read only · turn on Edit to change it',
		unsaved: 'Unsaved changes',
		editingNow: 'Editing',
		skillsFolder: 'Skills are folders under ~/.hera/skills/. Find more in the',
		skillsRepo: 'hera-skills repository',
		cancel: 'Cancel',
		version: (v: string) => `v${v.replace(/^v/, '')}`
	},

	models: {
		sameId: 'Id and name are the same',
		logoPick: 'Choose a picture',
		active: 'Active',
		activate: 'Use this one',
		add: 'Add an endpoint',
		name: 'Name',
		baseUrl: 'Base URL',
		model: 'Model id',
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
		pick: 'Add',
		unreachable: 'Could not reach it',
		remove: 'Remove',
		none: 'No endpoint registered yet. Add one and she has somewhere to think.',
		saved: 'Saved',
		nameRule: 'Lowercase letters, digits, - and _',

		kindLabel: 'Kind',
		kind: {
			openai: 'OpenAI',
			anthropic: 'Anthropic',
			google: 'Google',
			mistral: 'Mistral',
			openrouter: 'OpenRouter',
			lmstudio: 'LM Studio',
			ollama: 'Ollama',
			vllm: 'vLLM',
			llamacpp: 'llama.cpp',
			generic: 'Generic',
			custom: 'Custom'
		},

		logo: 'Logo',
		logoUpload: 'Upload a logo',
		logoClear: 'Remove logo',
		logoHint: 'PNG, JPEG, WebP or GIF.',

		modelsHeading: 'Registered models',
		modelId: 'Model id',
		modelName: 'Display name',
		addModel: 'Add model',
		removeModel: 'Remove',
		noModels: 'No models registered on this endpoint yet.',
		search: 'Search models…',
		alreadyAdded: 'Added',

		options: 'Request options',
		optionsHint:
			'Extra fields sent in the request body — for something this endpoint understands and Hera does not need to. Leave empty unless a model asks for one.',
		optionsRawHint: 'The same data as the fields above, and anything else this server takes.',
		optionsPreset: 'Known options',
		optionsPresetNone: 'Choose…',
		optionsInvalid: 'This is not valid JSON yet.',
		optionsSet: (count: number) => (count === 1 ? '1 option' : `${count} options`),
		optionsSave: 'Save options',
		optionsClear: 'Clear',

		// A structured form over the same opaque `options` bag (ADR 18) — Hera still does not
		// interpret these values, it just no longer makes typing them raw JSON the only way in.
		sampling: {
			temperature: 'Temperature',
			topP: 'Top P',
			topK: 'Top K',
			minP: 'Min P',
			repeatPenalty: 'Repeat penalty',
			reasoningEffort: 'Reasoning effort',
			reasoningEffortFree: 'low, high, whatever it takes',
			/** Where the vocabulary offered for this model came from. Shown because somebody
			 * looking at a control is entitled to know whether the endpoint said so or they did. */
			thinkingSource: {
				openrouter: 'Offered by OpenRouter',
				llamacpp: 'Offered by the model server',
				ollama: 'Offered by Ollama',
				litellm: 'Offered by LiteLLM',
				gemini: 'Offered by Google',
				declared: 'Told to Hera — nobody publishes this one',
				none: 'Nothing is known about this model yet'
			},
			thinking: 'Let her think',
			thinkingToggle: 'Let the model reason before it answers',
			thinkingBudget: 'Thinking budget (tokens)',
			/** How a vocabulary gets declared for the ~17 providers whose effort levels are
			 * documentation prose and no endpoint. Said plainly, because a hand-entered
			 * vocabulary is the one kind here that can be out of date without anything failing. */
			declare: 'Tell Hera what it accepts',
			declareHint:
				'Nobody publishes this, so it has to be said once. A level this model does not accept is refused by the server and fails the turn.',
			reasoningEffortHint:
				'A starting vocabulary — the values a server actually accepts are its own.',
			overrideNote:
				'A temperature or top P set here overrides the deployment’s own default for this model.',
			unset: 'Unset'
		},

		maxTokens: 'Max output tokens',
		maxTokensPlaceholder: 'Server default',
		maxTokensHint:
			'The most tokens one answer may run to, sent as max_tokens. Empty sends nothing, so the server’s own limit applies — some, like mlx_lm, stop at a few hundred by default and cut answers off mid-sentence. Overrides what the endpoint would otherwise use.',

		contextLength: 'Context window',
		contextLengthPlaceholder: 'e.g. 32768',
		contextLengthHint:
			'Tokens this model can hold, for the composer’s usage bar. Not probed — fill it in yourself; empty means no bar.',
		contextLengthInvalid: 'This should be a whole number greater than zero, or empty.',

		acceptsImages: 'Accepts images',
		acceptsImagesHint:
			'Whether this model can be shown a picture. Kept for later — nothing checks it yet, so images can still be attached to any model.',

		toolCalling: 'Uses tools',
		toolCallingHint:
			'Turn off for a model that writes what looks like a tool call instead of making one for real — it will only ever answer in prose, but cleanly instead of with a broken attempt.'
	},

	notifications: {
		finished: 'Hera has finished',
		heading: 'Notifications',
		toggle: 'Notify me when a turn finishes while this tab is hidden',
		denied: 'The browser has blocked notifications for this site. Allow them in its site settings.',
		unsupported: 'This browser cannot show notifications.'
	},

	account: {
		name: 'Name',
		namePlaceholder: 'What should she call you?',
		email: 'Email',
		emailPlaceholder: 'you@example.org',
		emailInvalid: 'That does not look like an email address.',
		avatar: 'Picture',
		upload: 'Upload a picture',
		replace: 'Replace picture',
		remove: 'Remove picture',
		avatarNote:
			'PNG, JPEG, WebP or GIF, up to 12 MB. It is cropped to a square and kept in your Hera folder.',
		tooBig: 'That picture is larger than 12 MB.',
		notAnImage: 'Choose a PNG, JPEG, WebP or GIF picture.',
		saved: 'Saved',
		security: 'Sign-in',
		securityNote: 'Hera has no login yet. These are drawn so you can see what is coming.',
		password: 'Password',
		twoFactor: 'Two-factor authentication',
		passkeys: 'Passkeys',
		later: 'Coming later'
	},

	general: {
		language: 'Language',
		languageNote:
			'The language of this interface. Which language she answers in is the language region under Mind.',
		timezoneNote: 'What she is told the date and time are. She is always told UTC as well.',
		aboutHeading: 'About',
		version: 'Version',
		dataFolder: 'Data folder',
		model: 'Model',
		english: 'English'
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
		copyCode: 'Copy code',
		copiedCode: 'Copied',
		showSource: 'Code',
		showDrawn: 'Preview',
		showSourceOf: (name: string) => `Show the code of ${name}`,
		showDrawnOf: (name: string) => `Show ${name} as drawn`,
		openFull: 'Full size',
		download: 'Download',
		/** The card's save control is a glyph, so its accessible name says *which* file — a turn
		 * that published four of them otherwise offers four identical buttons. */
		downloadOne: (name: string) => `Download ${name}`,
		/** A diagram is saved as the page that draws it, not as its mermaid source: what somebody
		 * saving a picture wants is the picture, and six lines of mermaid need a renderer they do
		 * not have. The control says so, because *Download* on a diagram and *Download* on a page
		 * would promise the same thing and give different ones. */
		downloadDrawn: 'Download as a page',
		downloadDrawnOne: (name: string) => `Download ${name} as a page`,
		close: 'Close',
		panel: 'Artifacts',
		view: 'Preview or source',
		toggle: 'Toggle side view',
		files: 'Everything published here',
		none: 'Nothing chosen yet.',
		loading: 'Fetching it…',
		count: (n: number) => (n === 1 ? '1 artifact' : `${n} artifacts`),
		/** Mermaid is fetched on demand, so the first diagram in a session waits on a download
		 * that later ones do not. Saying what is happening beats an empty box. */
		drawing: 'Drawing it…',
		/** A diagram that did not parse. The mermaid message carries the line number, which is
		 * the part a person can act on, and the source is shown under it — a `.mmd` file is
		 * still a file she made, and showing nothing at all is what makes one bad line look
		 * like an artifact that came out broken. */
		notDrawn: (why: string) => `That diagram did not come out: ${why}. The source is below.`,
		/** The pen: an edit switch that puts a text box over the file's source. */
		edit: 'Edit this file',
		save: 'Save',
		saved: 'Saved',
		saveFailed: (why: string) => `Could not save: ${why}`,
		discardTitle: 'Discard your changes?',
		discardBody: (name: string) => `${name} has edits that have not been saved.`,
		discardYes: 'Discard',
		discardKeep: 'Keep editing'
	},
	/** The chat's own menu in the top bar: what you can do with the conversation as a whole. */
	chatMenu: {
		label: 'Options for this chat',
		share: 'Share',
		/** Under Share, because a feature you can see coming is a promise (#101). */
		shareSoon: 'Coming later'
	},

	chat: {
		toolbar: 'Conversation tools',
		loading: 'Loading the conversation…',
		export: 'Export as Markdown'
	},

	empty: {
		title: 'Nothing here yet',
		chat: 'Say something to start.'
	},

	error: {
		load: 'Could not load that',
		send: 'The message did not go through',
		retry: 'Try again',
		retrying: 'Trying…'
	},

	/** The screen shown when the first load never answered. Its own block rather than more keys
	 * under `error`, because this is a whole screen with a voice and not a line of copy. */
	offline: {
		/** **Hera, not she.** The rest of the interface calls her *she*, and on this one screen it
		 * reads wrong: there is no conversation here and nothing has a voice — what has failed is
		 * a server, and the thing to name is the program you are about to restart. */
		title: 'Hera is not answering',
		/** Deliberately about *the server* and not about *the network*: this runs on the machine
		 * it talks to, so a failed request here almost always means a process is not running. */
		body: 'The interface is here, but nothing is listening behind it. If you started Hera yourself, check that the server is still running.',
		command: 'uv run hera serve',
		commandHint: 'The usual way to start Hera, from the project directory.',
		detail: 'What the browser said'
	},

	/** `+error.svelte`: an address that leads nowhere, and a screen that could not be drawn. */
	notFound: {
		title: 'Nothing here',
		body: 'This address does not lead to a chat, a project or a screen in Hera. It may have been deleted, or the link was mistyped.',
		home: 'Back to the start'
	},

	broken: {
		title: 'Something went wrong',
		body: 'Hera could not draw this screen. Reloading usually helps; if it does not, the detail below is what to report.',
		reload: 'Reload',
		home: 'Back to the start',
		detail: 'What went wrong'
	},

	/** The primitives in `lib/components/ui/`: words that belong to a control, not to a screen. */
	voice: {
		listening: 'Listening',
		muted: 'Muted',
		mute: 'Mute',
		unmute: 'Unmute',
		end: 'End'
	},
	imagegen: {
		queued: 'Queued',
		waiting: 'Waiting for the image model',
		step: (step: number, steps: number, percent: number) => `Step ${step} / ${steps} · ${percent}%`,
		failedAt: (step: number) => `Failed at step ${step}`,
		failed: 'Generation failed',
		done: (summary: string) => (summary ? `Done · ${summary}` : 'Done')
	},
	auth: {
		mode: 'Sign in or register',
		signIn: 'Sign in',
		register: 'Register',
		signInTitle: 'Sign in to Hera',
		registerTitle: 'Create your account',
		signInBlurb: 'Your chats stay on this machine either way.',
		registerBlurb: 'One account for every machine she runs on.',
		name: 'Name',
		email: 'Email',
		password: 'Password',
		passwordPlaceholder: 'At least 12 characters',
		passwordHelp: 'Or skip it and use a passkey.',
		continue: 'Continue',
		create: 'Create account',
		or: 'or',
		signInPasskey: 'Sign in with a passkey',
		registerPasskey: 'Register with a passkey'
	},
	errorPage: {
		offline: 'Offline',
		server: 'Server error',
		'not-found': '404 · Not found',
		model: 'Model unreachable'
	},
	ui: {
		close: 'Close',
		dismiss: 'Dismiss',
		loading: 'Loading',
		notResponding: 'Not responding',
		wait: 'Wait',
		retry: 'Try again',
		characters: 'characters',
		open: 'Open',
		closeSection: 'Collapse',
		openSection: 'Expand',
		clearSearch: 'Clear search',
		copy: 'Copy',
		copied: 'Copied',
		download: 'Download',
		edit: 'Edit',
		preview: 'Preview',
		source: 'Source',
		zoomIn: 'Zoom in',
		zoomOut: 'Zoom out',
		resetZoom: 'Reset zoom',
		remove: (name: string) => `Remove ${name}`,
		uploading: 'uploading',
		stalledFor: (seconds: number) => `Nothing has arrived for ${seconds} seconds.`,
		startedAgo: (seconds: number) => `Started ${seconds} seconds ago`
	}
} as const;

export function greetingFor(date: Date = new Date(), name = ''): string {
	const hour = date.getHours();
	const phrase =
		hour < 5
			? t.greeting.night
			: hour < 12
				? t.greeting.morning
				: hour < 18
					? t.greeting.afternoon
					: t.greeting.evening;
	return name ? `${phrase}, ${name}` : phrase;
}

/** "12 ms", "1.4 s" — a duration a person reads rather than a number they convert. */
export function duration(ms: number): string {
	if (ms < 1000) return `${ms} ms`;
	return `${(ms / 1000).toFixed(1)} s`;
}
