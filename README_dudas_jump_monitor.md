# Dudas Jump Leaderboard Monitor

This read-only Python monitor checks the public Webcade Dudas Jump endpoint continuously and sends the top 10 scores to a Telegram group **when they change**. It does not log in, connect to a wallet, submit scores, or place trades.

## Endpoint verified

```text
https://webcade.fun/api/dudas/board?limit=10&window=today
```

## Setup

Install the one dependency:

```bash
python3 -m pip install requests
```

Create a Telegram bot with [@BotFather](https://t.me/BotFather), add it to your group, and give it permission to send messages. Do not put a seed phrase, private key, or Webcade credentials in this script.

```bash
export TELEGRAM_BOT_TOKEN=token-from-botfather
export TELEGRAM_CHAT_ID=-1001234567890
# Optional: only for a Telegram forum topic
export TELEGRAM_MESSAGE_THREAD_ID=123
```

Run it:

```bash
python3 /home/ubuntu/dudas_jump_monitor.py
```

The script polls every 5 seconds by default, all day and every day. You can override this with `DUDAS_INTERVAL_SECONDS`, including decimal values such as `DUDAS_INTERVAL_SECONDS=0.1` for a 100-millisecond interval; the value must be greater than zero. For example, `DUDAS_INTERVAL_SECONDS=60` is gentler on the public endpoint. It saves a local baseline in `dudas_jump_state.json`, then sends a Telegram message only after a later response changes in rank, player, score, height, toad count, or run duration. It records each score version’s first-observed UTC time with millisecond precision and includes that timestamp in the alert. The public API does not expose a guaranteed server-side submission timestamp, so first-observed time is the monitor’s submission-time estimate. It intentionally does not send a message on the first baseline check.

## Keeping it running

For reliable overnight monitoring, run it on a computer or server that stays online. A local laptop that sleeps will not receive updates. If you use a hosted service, review its privacy and bot-token handling first.

## Simple Railway deployment

1. Create a GitHub repository and upload these files: `dudas_jump_monitor.py`, `requirements.txt`, `Procfile`, `railway.toml`, and `nixpacks.toml`.
2. The supplied `requirements.txt` contains this compatible dependency range:

   ```text
   requests>=2.31,<3
   ```

3. Create a Telegram bot with [@BotFather](https://t.me/BotFather), add it to your group, and give it permission to send messages.
4. In Railway, choose **New Project → Deploy from GitHub repo**, then select the repository.
5. The included `Procfile` and `railway.toml` already define the worker start command. If Railway asks for it manually, use:

   ```text
   python dudas_jump_monitor.py
   ```

6. In Railway’s **Variables** section, add:

   ```text
   TELEGRAM_BOT_TOKEN=token-from-botfather
   TELEGRAM_CHAT_ID=-1001234567890
   DUDAS_INTERVAL_SECONDS=5
   ```

7. Deploy. Open Railway logs and confirm `Continuous read-only mode` and `Baseline saved` appear.
8. Change a test leaderboard entry or wait for a real change; the bot should post the updated top 10 to the group.

Never upload `.env`, a bot token, a private key, or any other credential to GitHub. Put secrets only in Railway Variables.

This is a Python worker, not an npm project. Do **not** run `npm build` and do not add a dummy `package.json`; that can cause Railway to detect the wrong build system. Railway uses the native Nix `python311Packages.requests` dependency declared in `nixpacks.toml`, avoiding pip writes to the immutable system environment.

### If Railway still reports deployment failure

Check the failed deployment log, not only the service log. The build should show Python and `python311Packages.requests` being installed. The runtime start command should be exactly `python dudas_jump_monitor.py`, from the repository root. Confirm the repository contains the `.py` file at its top level, not inside an extra nested folder. Confirm Railway Variables include both `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`. A missing Telegram variable does not normally prevent the initial baseline, but it will prevent notifications when a change occurs.

If Railway cannot detect the project, redeploy after committing all five files. The project does not require Node.js, npm, a web server, a port, a database, Docker, or a health-check URL.

## Railway, Vercel, and free hosting

**Railway can run this as a worker**, but it is not permanently free: Railway currently advertises a limited trial and a small monthly free allowance, subject to its current pricing and account eligibility. A worker is the correct Railway service type because this program stays alive and polls continuously; Railway cron jobs are intended for tasks that start, run, and terminate.

**Vercel is not a good fit for this exact script.** Vercel Functions are request-invoked and have execution-duration limits, so an infinite polling loop will be terminated. Vercel could host a short endpoint, but you would need an external scheduler and persistent state, making it more complicated.

For a genuinely free 24/7 VM, investigate an eligible **Oracle Cloud Always Free** instance. AWS Free Tier can also work if the account is eligible, but create a billing alert because usage outside the allowance can incur charges. DigitalOcean is convenient but normally relies on temporary trial credits rather than a permanent free server.

If deploying to Railway, configure the service with:

```text
Start command: python dudas_jump_monitor.py
TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID: Railway Variables
DUDAS_INTERVAL_SECONDS: 5 (supports decimal values such as 0.1)
```

Do not commit `.env`, a bot token, a private key, or any other credential to a repository. Set secrets through the platform’s encrypted variable store.

## Finding the group chat ID

After adding the bot to the group, send a message in that group. Then open this read-only Telegram endpoint, replacing the token:

```text
https://api.telegram.org/botYOUR_BOT_TOKEN/getUpdates
```

Look for `message.chat.id`. Supergroups commonly have a negative ID beginning with `-100`. Treat the bot token like a password and never publish it. If the bot cannot see messages, check its group permissions and privacy settings in BotFather. For a forum topic, set `TELEGRAM_MESSAGE_THREAD_ID` as well.

## Can it see scores while people are still playing?

I inspected the public game page and its JavaScript. The exposed leaderboard endpoint is:

```text
https://webcade.fun/api/dudas/board?limit=10&window=today
```

It returns completed/saved leaderboard runs. I did not find a public endpoint that exposes other players’ live, in-progress scores. The page’s “Your progress” section is user-specific and does not provide a public live feed. Therefore, this monitor cannot reliably report scores before a run is submitted or saved. That would require an official Webcade live-events/WebSocket endpoint or permission from Webcade.

## Notification limitation

The public endpoint exposes the current leaderboard, not a guaranteed event stream or server-side `submittedAt` timestamp for every score submission. The monitor therefore reports the first-observed UTC time, which is the closest submission-time estimate available from this public API. A score may not trigger an alert if it does not enter or change the top 10, if the endpoint updates late, or if the request is rate-limited.

## Important limitation

This uses the currently public, undocumented endpoint exposed by the webpage. Webcade could change or remove it without notice. The monitor prints failures and continues, but it cannot guarantee delivery if the endpoint, network, or Telegram service is unavailable.
