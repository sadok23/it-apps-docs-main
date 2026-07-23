#!/usr/bin/env python3
import re
import gitlab
import ldap3

# ─── Configuration ────────────────────────────────────────────────────────────

GITLAB_URL   = 'http://20.0.0.132:8080'
GITLAB_TOKEN = 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXx'

LDAP_HOST    = 'ipa.asteroidea.co'
LDAP_BIND_DN = 'uid=admin,cn=users,cn=accounts,dc=asteroidea,dc=co'
LDAP_PASS    = 'Asteroidea4711$%!'
LDAP_BASE    = 'cn=groups,cn=accounts,dc=asteroidea,dc=co'

ROLE_LEVELS = {
    'developper': 30,
    'maintainer': 40,
    'owner':      50,
    'reporter':   20,
    'guest':      10,
}

PROTECTED_USERS = {'admin', 'root'}

# ─── Client Initialization ────────────────────────────────────────────────────

def init_gitlab() -> gitlab.Gitlab:
    return gitlab.Gitlab(GITLAB_URL, private_token=GITLAB_TOKEN)


def init_ldap() -> ldap3.Connection:
    server = ldap3.Server(LDAP_HOST, get_info=ldap3.ALL)
    return ldap3.Connection(server, LDAP_BIND_DN, LDAP_PASS, auto_bind=True)

# ─── LDAP Helpers ─────────────────────────────────────────────────────────────

def fetch_ipa_memberships(conn: ldap3.Connection) -> dict:
    """
    Query FreeIPA for all groups matching 'gitlab-*'.
    Returns: { project_name: { username: access_level } }
    """
    conn.search(
        LDAP_BASE,
        '(&(objectClass=ipausergroup)(cn=gitlab-*))',
        attributes=['cn', 'member'],
    )

    memberships = {}

    for entry in conn.entries:
        cn    = str(entry.cn)
        parts = cn.split('-')

        if len(parts) < 3:
            continue

        project  = '-'.join(parts[1:-1])
        role_key = parts[-1]

        if role_key not in ROLE_LEVELS:
            print(f"[SKIP] {cn}: unknown role '{role_key}'")
            continue

        level = ROLE_LEVELS[role_key]
        memberships.setdefault(project, {})

        for member_dn in entry.member:
            match = re.search(r'uid=([^,]+)', member_dn)
            if not match:
                continue
            username      = match.group(1)
            current_level = memberships[project].get(username, 0)
            if level > current_level:
                memberships[project][username] = level

    return memberships

# ─── GitLab Helpers ───────────────────────────────────────────────────────────

def get_or_create_group(gl: gitlab.Gitlab, project: str):
    """Return existing GitLab group by path, or create it."""
    for g in gl.groups.list(search=project):
        if g.path == project:
            return g

    group = gl.groups.create({'name': project.capitalize(), 'path': project})
    print(f"[NEW GROUP] {project}")
    return group


def sync_group_members(group, desired: dict, gl: gitlab.Gitlab):
    """
    Reconcile GitLab group membership against the desired state from FreeIPA.
    - Adds missing members
    - Updates changed access levels
    - Removes members no longer in IPA
    """
    current = {m.username: m for m in group.members.list(all=True)}

    # Add / update
    for username, level in desired.items():
        if username in PROTECTED_USERS:
            continue

        if username in current:
            member = current[username]
            if member.access_level != level:
                member.access_level = level
                member.save()
                print(f"  [~] {username} → level {level}")
        else:
            users = gl.users.list(username=username)
            if users:
                group.members.create({'user_id': users[0].id, 'access_level': level})
                print(f"  [+] {username} added at level {level}")
            else:
                print(f"  [!] {username} not in GitLab (first login required)")

    # Remove
    for username, member in current.items():
        if username not in PROTECTED_USERS and username not in desired:
            group.members.delete(member.id)
            print(f"  [-] {username} removed")

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    gl   = init_gitlab()
    conn = init_ldap()

    memberships = fetch_ipa_memberships(conn)

    for project, desired_members in memberships.items():
        print(f"\n[SYNC] {project}")
        try:
            group = get_or_create_group(gl, project)
            sync_group_members(group, desired_members, gl)
        except Exception as exc:
            print(f"  [ERROR] {project}: {exc}")

    conn.unbind()


if __name__ == '__main__':
    main()