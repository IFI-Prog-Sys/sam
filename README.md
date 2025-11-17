# Sam the Scraper
Prog.Sys();'s one and only Progsys scraper bot

## Basic Overview
Sam is a Python bot that pulls event metadata for the specified organization from Peoply.app and posts it in a
Discord channel.

The bot runs on Python, but is launched and managed by systemd.

## File structure
**Note:** Only files necessary for runtime are included
```
sam/
├── discord_gateway.py
├── main.py
├── sam.py
└── secrets.json
```

## Getting started
**Note:** Sam has currently been tested on Python 3.13.8 running on NixOS 25.05

1. Create an application in the Discord Developer Portal
2. Copy the secret application API key to the value under "discord\_api\_key:" in secrets.json
3. Copy your server's desired output channel ID to the value under "channel\_id:" in secrets.json
4. Invite your new Discord application into your server with the following permissions:
    - View Channels
    - Send Messages
    - Send Messages in Threads
    - Attach Files
    - Mention @everyone, @here and All Roles
    - **Note:** There is a good chance not all these permissions are strictly speaking necessary but these are what have worked for us.
6. Edit "sam.service" and specify the "ExecStart" target (main.py) and "WorkingDirectory (path to sam files)"
7. Copy the provided sam.service file into "/etc/systemd/user/" 
8. Start the service by running
```bash
$ systemctl --user start sam.service
```
9. *(optional)* Enable auto startup by running:
```bash
$ systemctl --user enable sam.service
```
**Warning:** Sam's event memory is not yet persistent so duplicate messages may occur after reboot.
