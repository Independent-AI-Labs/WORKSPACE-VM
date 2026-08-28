# Workspace Automation

These scripts synchronize one Tabby profile per workspace project, open all
profiles in Tabby, and provide a launcher for the desktop menu

## Setup

```bash
cd scripts/workspace-automation
cp .env.example .env
$EDITOR .env
chmod 600 .env
```

Set the SSH host, credentials, workspace paths, and any Tabby command/process
overrides in `.env`. Passwords are read from the environment by `expect`; they
are not passed as command-line arguments or written to Tabby configuration.

## Use

```bash
./sync-tabby-profiles.sh
./open-workspaces.sh
./pin-to-dock.sh
```

Linux uses Tabby's XDG configuration directory and `xdg-open` for the
`tabby://` links. macOS keeps the native Tabby URL handling and installs an
`.app` launcher in the Dock. Both platforms require Tabby, OpenSSH, and
`expect`; Linux additionally requires `xdg-open` and `xdg-desktop-menu`.
