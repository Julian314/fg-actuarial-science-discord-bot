# Setting up the Discord application

Before the bot can run, Discord needs to know about it. You create an **application** with a
**bot user**, copy its **token** into `.env`, and **invite** the bot to your server. You only do
this once.

## 1. Create the application

1. Open the [Discord Developer Portal](https://discord.com/developers/applications) and log in.
2. Click **New Application**, give it a name (e.g. "FG Actuarial Bot") and accept the terms.
3. Optional: on **General Information**, upload an avatar and add a description.

## 2. Get the bot token

1. In the left menu, open **Bot**.
2. Click **Reset Token** and confirm. Copy the token that appears.
3. Paste it into your `.env` file:

   ```dotenv
   DISCORD_TOKEN=MTIz...your-token...
   ```

> **Treat the token like a password.** Anyone with it can control your bot. Never commit it,
> never paste it in a chat. If it leaks, click **Reset Token** again: the old one stops working
> immediately. `.env` is listed in `.gitignore`, so git ignores it.

### Privileged intents: none needed

On the same **Bot** page you can leave **Presence Intent**, **Server Members Intent** and
**Message Content Intent** turned **off**. The bot only uses slash commands and voice states,
which need no privileged intents. (The old bot needed them for prefix commands and a joke
feature; see [migration-from-old-bot.md](migration-from-old-bot.md).)

## 3. Invite the bot to your server

1. Open **OAuth2 → URL Generator**.
2. Under **Scopes**, tick `bot` and `applications.commands`.
3. Under **Bot Permissions**, tick:

   | Permission | Needed for |
   |---|---|
   | View Channels | seeing the channels it should post in |
   | Send Messages | replies, "Now playing", the job report |
   | Embed Links | all the nicely formatted messages |
   | Attach Files | chess board images, the Markdown job report |
   | Connect | joining voice channels |
   | Speak | playing music |

4. Open the generated URL, pick your server and confirm.

Shortcut: this URL requests exactly those permissions. Replace `YOUR_APPLICATION_ID` with the
**Application ID** from **General Information**:

```
https://discord.com/oauth2/authorize?client_id=YOUR_APPLICATION_ID&scope=bot+applications.commands&permissions=3197952
```

## 4. Copy the server and channel IDs

IDs are long numbers that identify servers, channels and users. To copy them:

1. In Discord: **User Settings → Advanced → Developer Mode** → on.
2. **Server ID:** right-click the server icon → **Copy Server ID** → `GUILD_ID` in `.env`.
3. **Channel ID:** right-click the text channel for the job report → **Copy Channel ID** →
   `JOBS_CHANNEL_ID` in `.env`.

`GUILD_ID` is optional but recommended. With it, slash commands show up in your server
**immediately**. Without it they are registered globally, which can take up to an hour the first
time. Use global registration only if the bot should work in several servers.

## 5. Start the bot

```bash
uv run fgbot
```

You should see a line like `Logged in as FG Actuarial Bot#1234 … in 1 server(s)`. Type `/` in
your server and the bot's commands appear. Try `/ping`.

## Who may use which command

Most commands are available to everyone. Some are restricted by default, either because they
affect everyone or because they are expensive:

| Command | Default requirement |
|---|---|
| `/stop`, `/summon`, `/leave` | Manage Server permission |
| `/jobs run-now` | Manage Server permission |

Server admins can change this without touching the code. Go to **Server Settings → Integrations →
(your bot)** and allow or deny any command for specific roles, members or channels. You can, for
example, allow the job commands only in the job channel.
