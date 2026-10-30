<script lang="ts">
	/**
	 * Settings → Admin → Users: everybody who can sign in here (ADR 27).
	 *
	 * Inviting is at the top, because making somebody an account is what an admin comes here to
	 * do most. Each row says who they are and what state they are in — an admin, invited and not
	 * yet arrived, disabled — and keeps the rest in one menu: a role, a fresh link, signing them
	 * out, disabling. Deleting is a button of its own on the row, and rows can be selected to
	 * delete several people at once — managing a team means removing people who left, and doing
	 * that one menu at a time does not scale. Your own row has neither, since both are ways to
	 * lock yourself out, and the server refuses them anyway.
	 *
	 * Deleting asks first, once for the whole selection, and says what goes with the accounts;
	 * disabling is the way to keep it all. The deletes run one after another, and somebody the
	 * server refused — the last admin, say — is named with the reason while the rest still go.
	 */
	import { api, type AdminUser, type Sent } from '$lib/api/client';
	import Avatar from '$lib/components/ui/Avatar.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import Checkbox from '$lib/components/ui/Checkbox.svelte';
	import Confirm from '$lib/components/ui/Confirm.svelte';
	import IconButton from '$lib/components/ui/IconButton.svelte';
	import Menu from '$lib/components/ui/Menu.svelte';
	import MenuItem from '$lib/components/ui/MenuItem.svelte';
	import Pill from '$lib/components/ui/Pill.svelte';
	import { t } from '$lib/i18n';
	import { Placeholder } from '$lib/loading.svelte';
	import { workspace } from '$lib/stores/workspace.svelte';
	import { copyText } from '$lib/clipboard';
	import { toasts } from '$lib/toasts.svelte';
	import InviteForm from './InviteForm.svelte';
	import LoadFailed from './LoadFailed.svelte';
	import Rows from './Rows.svelte';
	import SentLink from './SentLink.svelte';

	interface Props {
		filter?: string;
	}

	let { filter = '' }: Props = $props();

	let users = $state<AdminUser[]>([]);
	let failed = $state<unknown>(null);
	let error = $state<string | null>(null);
	let menuFor = $state<string | null>(null);
	let anchors = $state<Record<string, HTMLElement | null>>({});
	/** Who the confirmation is asking about: one row's button, or the selection. */
	let deleting = $state<AdminUser[] | null>(null);
	let removing = $state(false);
	let selected = $state<string[]>([]);
	/** The link last made for somebody, shown under their row until the screen is left. */
	let sent = $state<Record<string, Sent>>({});

	const me = $derived(workspace.account?.id ?? '');
	const visible = $derived(
		users.filter(
			(user) =>
				!filter ||
				user.email.toLowerCase().includes(filter) ||
				user.name.toLowerCase().includes(filter)
		)
	);

	/** Everybody shown who could be deleted — not you. */
	const deletable = $derived(visible.filter((user) => user.id !== me));
	const chosen = $derived(users.filter((user) => selected.includes(user.id)));
	const allChosen = $derived(
		deletable.length > 0 && deletable.every((user) => selected.includes(user.id))
	);

	function pick(user: AdminUser, on: boolean) {
		selected = on ? [...selected, user.id] : selected.filter((id) => id !== user.id);
	}

	function pickAll(on: boolean) {
		const shown = deletable.map((user) => user.id);
		selected = on
			? [...new Set([...selected, ...shown])]
			: selected.filter((id) => !shown.includes(id));
	}

	const settling = new Placeholder(true);
	$effect(() => () => settling.stop());

	async function load() {
		failed = null;
		settling.set(true);
		try {
			users = await api.users();
		} catch (cause) {
			failed = cause;
		} finally {
			settling.set(false);
		}
	}
	void load();

	const who = (user: AdminUser) => user.name || user.email;

	async function act(work: () => Promise<void>) {
		menuFor = null;
		error = null;
		try {
			await work();
		} catch (cause) {
			error = cause instanceof Error ? cause.message : String(cause);
		}
	}

	function replace(changed: AdminUser): void {
		users = users.map((user) => (user.id === changed.id ? changed : user));
	}

	const setRole = (user: AdminUser) =>
		act(async () =>
			replace(await api.updateUser(user.id, { role: user.role === 'admin' ? 'user' : 'admin' }))
		);
	const setDisabled = (user: AdminUser) =>
		act(async () => replace(await api.updateUser(user.id, { disabled: !user.disabled })));
	const link = (user: AdminUser) =>
		act(async () => {
			sent = { ...sent, [user.id]: await api.sendLink(user.id) };
		});
	/** A new link, copied rather than mailed — for a mail that is slow or never came. Shown under
	 * the row as well, for the browser that would not copy it. */
	function copyLink(user: AdminUser) {
		menuFor = null;
		error = null;
		const made = api.sendLink(user.id, { mail: false });
		void made.then(
			(link) => (sent = { ...sent, [user.id]: link }),
			(cause) => (error = cause instanceof Error ? cause.message : String(cause))
		);
		void copyText(made.then((link) => link.link)).then((copied) =>
			toasts.show(copied ? t.admin.copiedNew : t.admin.copyFailed)
		);
	}

	const signOut = (user: AdminUser) =>
		act(async () => {
			await api.signOutUser(user.id);
			toasts.show(t.admin.signedOut(who(user)));
			await load();
		});

	async function remove() {
		const going = deleting ?? [];
		deleting = null;
		menuFor = null;
		error = null;
		removing = true;
		const refused: string[] = [];
		for (const user of going) {
			try {
				await api.deleteUser(user.id);
				users = users.filter((each) => each.id !== user.id);
				selected = selected.filter((id) => id !== user.id);
			} catch (cause) {
				refused.push(
					t.admin.deleteFailed(who(user), cause instanceof Error ? cause.message : String(cause))
				);
			}
		}
		removing = false;
		if (refused.length) error = refused.join(' ');
	}

	function seen(user: AdminUser): string {
		return user.last_seen_at
			? t.admin.lastSeen(new Date(user.last_seen_at).toLocaleString())
			: t.admin.notSignedIn;
	}
</script>

<section>
	<h3>{t.admin.invite}</h3>
	<p class="caption">{t.admin.inviteBlurb}</p>
	<InviteForm admin oninvited={() => void load()} />
</section>

{#if error}<p class="error" role="alert">{error}</p>{/if}

{#if settling.shown}
	<Rows label={t.settings.loading} />
{:else if failed !== null}
	<LoadFailed cause={failed} what={t.loadFailed.what.users} onretry={load} />
{:else}
	{#if deletable.length > 0}
		<div class="bar">
			<Checkbox checked={allChosen} label={t.admin.selectAll} onchange={(on) => pickAll(on)} />
			{#if chosen.length > 0}
				<span class="count">{t.admin.selected(chosen.length)}</span>
				<Button
					size="sm"
					variant="danger-soft"
					icon="trash"
					busy={removing}
					onclick={() => (deleting = chosen)}>{t.admin.deleteSelected}</Button
				>
			{/if}
		</div>
	{/if}
	<ul class="users">
		{#each visible as user (user.id)}
			<li>
				<div class="row">
					{#if user.id !== me}
						<Checkbox
							checked={selected.includes(user.id)}
							ariaLabel={t.admin.select(who(user))}
							onchange={(on) => pick(user, on)}
						/>
					{:else}
						<span class="spacer"></span>
					{/if}
					<Avatar name={who(user)} size={32} />
					<span class="who">
						<span class="name">{who(user)}</span>
						<span class="line">{user.name ? `${user.email} · ` : ''}{seen(user)}</span>
					</span>
					<span class="pills">
						{#if user.id === me}<Pill>{t.admin.you}</Pill>{/if}
						{#if user.role === 'admin'}<Pill tone="authority">{t.admin.roleAdmin}</Pill>{/if}
						{#if user.invited}<Pill tone="live">{t.admin.invited}</Pill>{/if}
						{#if user.disabled}<Pill tone="danger">{t.admin.disabled}</Pill>{/if}
					</span>
					{#if user.id !== me}
						<IconButton
							icon="trash"
							size="sm"
							label={t.admin.deleteOne(who(user))}
							disabled={removing}
							onclick={() => (deleting = [user])}
						/>
						<IconButton
							icon="more"
							size="sm"
							label={t.admin.actions(who(user))}
							bind:ref={anchors[user.id]}
							onclick={() => (menuFor = menuFor === user.id ? null : user.id)}
						/>
						<Menu
							open={menuFor === user.id}
							anchor={anchors[user.id] ?? null}
							label={t.admin.actions(who(user))}
							align="end"
							onclose={() => (menuFor = null)}
						>
							<MenuItem icon="shield" onclick={() => setRole(user)}>
								{user.role === 'admin' ? t.admin.makeUser : t.admin.makeAdmin}
							</MenuItem>
							{#if !user.disabled}
								<MenuItem icon="mail" onclick={() => link(user)}>
									{user.invited ? t.admin.newInvitation : t.admin.resetLink}
								</MenuItem>
								<MenuItem icon="copy" onclick={() => copyLink(user)}>
									{user.invited ? t.admin.copyInvitation : t.admin.copyReset}
								</MenuItem>
								<MenuItem icon="exit" onclick={() => signOut(user)}>{t.admin.signOut}</MenuItem>
							{/if}
							<MenuItem icon="lock" onclick={() => setDisabled(user)}>
								{user.disabled ? t.admin.enable : t.admin.disable}
							</MenuItem>
						</Menu>
					{/if}
				</div>
				{#if sent[user.id]}<SentLink sent={sent[user.id]} email={user.email} />{/if}
			</li>
		{:else}
			<p class="empty">{t.settings.noMatch}</p>
		{/each}
	</ul>
{/if}

{#if deleting}
	<Confirm
		title={deleting.length === 1
			? t.admin.deleteTitle(who(deleting[0]))
			: t.admin.deleteManyTitle(deleting.length)}
		body={deleting.length === 1 ? t.admin.deleteBody : t.admin.deleteManyBody}
		confirm={t.admin.deleteYes}
		cancel={t.admin.keep}
		onconfirm={remove}
		oncancel={() => (deleting = null)}
	/>
{/if}

<style>
	section {
		padding: 14px 0;
		border-bottom: 1px solid var(--line);
	}

	h3 {
		margin: 0 0 4px;
		font-size: 14px;
		font-weight: 500;
	}

	.caption {
		margin: 0 0 12px;
	}

	.bar {
		display: flex;
		align-items: center;
		gap: 12px;
		min-height: 36px;
		padding: 10px 0;
		border-bottom: var(--border-width) solid var(--line);
	}

	.count {
		margin-left: auto;
		color: var(--text-muted);
		font-size: 12.5px;
	}

	/* Your own row has no checkbox; this keeps its avatar in line with everybody else's. */
	.spacer {
		flex: none;
		width: 17px;
	}

	.users {
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.users li {
		padding: 10px 0;
		border-bottom: var(--border-width) solid var(--line);
	}

	.row {
		display: flex;
		align-items: center;
		gap: 12px;
	}

	.who {
		display: flex;
		flex: 1;
		flex-direction: column;
		min-width: 0;
	}

	.name,
	.line {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.name {
		font-size: 13.5px;
	}

	.line {
		color: var(--text-faint);
		font-size: 12px;
	}

	.pills {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
	}

	.error {
		margin: 12px 0 0;
		color: var(--danger);
		font-size: 13px;
	}

	.empty {
		margin: 18px 0;
		color: var(--text-muted);
	}
</style>
