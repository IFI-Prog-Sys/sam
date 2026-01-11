# Sam the Scraper
A Python bot by Prog.Sys(); for scraping event metadata from Peoply.app.

## Basic Overview
Sam is a Python bot that pulls event metadata for the specified organization from Peoply.app and posts it in a
Discord channel.

The bot runs on Python, but is launched and managed by systemd.

## Key Files (Runtime)
```
sam/
├── config.yaml
├── discord_gateway.py
├── main.py
└── sam.py
```

## Prerequisites
Sam requires Python >= 3.10.

**Note:** Sam has been tested on Python 3.13.8 (NixOS 25.05) and Python 3.12.9 (Oracle Linux Server release 9.6).

## Setup

Follow these steps to set up and run Sam:

### 1. Install Dependencies
Install the required Python packages:
```bash
pip install -r requirements.txt
```

### 2. Discord Application Setup
1. Create a new application in the Discord Developer Portal.
2. Obtain your Discord Application API key. This key must be provided as the `SAM_API_KEY` environment variable when running Sam.
3. Invite your new Discord application to your server with the following permissions:
    - View Channels
    - Send Messages
    - Send Messages in Threads
    - Attach Files
    - Mention @everyone, @here and All Roles
    **Note:** Not all of these permissions may be strictly necessary, but they have proven to work.

### 3. Configuration
Edit `config.yaml` to set the following:
- `organization_name`
- `channel_id`
- `database_path`
- `expose_api`

### 4. Systemd Service Setup
1. Locate `sam.service` under the `install_files/` directory.
2. Edit `sam.service` to specify:
    - `ExecStart` path (e.g., `python3 /path/to/main.py`)
    - `WorkingDirectory` (path to Sam's files)
    - The `SAM_API_KEY` environment variable
    - Confirm the `Restart` policy is set to `always`
3. Copy the configured `sam.service` file into `/etc/systemd/user/`.

### 5. Running the Service
Start the Sam service:
```bash
systemctl --user start sam.service
```

### 6. (Optional) Enable Auto-startup
To automatically start Sam on system boot:
```bash
systemctl --user enable sam.service
```

## Additional Notes
Sam uses a SQLite database to persist event history across restarts.
