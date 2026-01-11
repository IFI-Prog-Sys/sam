# Sam the Scraper
Prog.Sys();'s one and only Peoply scraper bot

## Basic Overview
Sam is a Python bot that pulls event metadata for the specified organization from Peoply.app and posts it in a
Discord channel.

The bot runs on Python, but is launched and managed by systemd.

## File structure
**Note:** Only files necessary for runtime are included
```
sam/
├── config.yaml
├── discord_gateway.py
├── main.py
└── sam.py
```

## Getting started
__**Warning:** Sam requires Python >= 3.10__

**Note:** Sam has currently been tested on Python 3.13.8 running on NixOS 25.05, and on Python 3.12.9 running on Oracle Linux Server release 9.6

1. Install all the project dependencies with:
```bash
$ pip install -r requirements.txt
```
**Note:** If you prefer; a nix.shell file can be found on the development branch.

2. Create an application in the Discord Developer Portal
3. Edit `config.yaml` and set the `organization_name`, `channel_id`, `database_path`, and `expose_api`.
4. Obtain your Discord Application API key. This will need to be provided as the `SAM_API_KEY` environment variable.
5. Invite your new Discord application into your server with the following permissions:
    - View Channels
    - Send Messages
    - Send Messages in Threads
    - Attach Files
    - Mention @everyone, @here and All Roles
    - **Note:** There is a good chance not all these permissions are strictly speaking necessary but these are what have worked for us.
6. Edit "sam.service" (found under "install\_files"):
    - Specify the `ExecStart` path (python3 and main.py)
    - Specify the `WorkingDirectory` (path to sam files)
    - Set the `SAM_API_KEY` environment variable
    - Confirm the `Restart` policy is set to `always`
7. Copy the provided sam.service file into "/etc/systemd/user/" 
8. Start the service by running
```bash
$ systemctl --user start sam.service
```
9. *(optional)* Enable auto startup by running:
```bash
$ systemctl --user enable sam.service
```
**Note:** Sam uses a SQLite database to persist event history across restarts.
