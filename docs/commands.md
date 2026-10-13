# Commands

All commands are **slash commands**. Type `/` in Discord and pick the bot's command; Discord
shows the arguments and checks them for you (e.g. volume must be 0–100). `/help` lists every
command directly in Discord.

Replies to errors and to purely personal commands (like `/chess hint`) are **ephemeral**: only you
can see them.

## General

| Command | Description |
|---|---|
| `/help` | List all commands. |
| `/ping` | Check that the bot is alive and see its latency. |
| `/about` | Version, uptime and which features are enabled. |

## 🎵 Music

You need to be in a voice channel. Once the bot is playing, only people in **the same** voice
channel can control it.

| Command | Description |
|---|---|
| `/play <query>` | Play or queue a song. `query` can be search text (`daft punk one more time`), a YouTube URL or another site [supported by yt-dlp](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md), or a Spotify track, album or playlist link. The bot joins your channel if needed. |
| `/join` | Join your voice channel. |
| `/summon [channel]` | Move the bot to a voice channel (default: yours). *Manage Server.* |
| `/leave` | Clear the queue and leave. *Manage Server.* |
| `/pause` / `/resume` | Pause or resume playback. |
| `/skip` | Skip the current song (also when loop is on). |
| `/stop` | Stop playback and clear the queue, but stay in the channel. *Manage Server.* |
| `/now` | Show the song that is playing. |
| `/queue [page]` | Show the queue, 10 songs per page. |
| `/remove <position>` | Remove the song at a position shown by `/queue`. |
| `/shuffle` | Shuffle the queue. |
| `/loop` | Repeat the current song on or off. |
| `/volume <0-100>` | Change the volume. It takes effect immediately. |

The bot leaves automatically when everybody else has left the voice channel, and after
`MUSIC_IDLE_TIMEOUT` seconds (default 5 minutes) without music.

## ♟️ Chess

You play against **ShessGPT** (see [chess-engine.md](chess-engine.md)). Each text channel can have
one game at a time, and only the player who started it can move.

| Command | Description |
|---|---|
| `/chess start [color] [fen]` | Start a game. `color`: `white` (default), `black` or `random`. `fen`: optionally start from a position, e.g. one copied from lichess. If it's the bot's turn, it moves right away. |
| `/chess move <move>` | Make your move. Use SAN (`e4`, `Nf3`, `O-O`, `exd5`, `e8=Q`) or UCI (`e2e4`, `g1f3`). Discord **autocompletes legal moves** while you type. ShessGPT replies immediately. |
| `/chess undo` | Take back your last move and ShessGPT's reply. |
| `/chess override <move>` | Replace ShessGPT's last move with a move you choose, to explore "what if it had played …". |
| `/chess hint` | Best move for the side to move, according to Stockfish and ShessGPT (only you see it). |
| `/chess eval` | How good is the position? Positive numbers mean White is better, in pawns. |
| `/chess board` | Show the board again. |
| `/chess fen` | The position as a FEN string, e.g. to analyse it on lichess.org. |
| `/chess resign` | End the game. The player or anyone with *Manage Messages* can do this, so moderators can clean up abandoned games. |

The board is drawn from your side, so Black is at the bottom when you play Black. The last move is
highlighted, and a king in check is marked red. Games are kept in memory, so restarting the bot
ends all running games.

## 💼 Job reports

The daily report is posted automatically; see [job-reports.md](job-reports.md). These commands
let you look at the data at any time. Their replies are only visible to you.

| Command | Description |
|---|---|
| `/jobs list [category] [canton] [seniority] [limit]` | Open matching jobs, best match first. Without filters it uses the scraper's default filter (entry-level and unspecified seniority). Example: `/jobs list category:Actuarial canton:ZH`. |
| `/jobs search <text>` | Open jobs whose title or company contains the text, e.g. `/jobs search Swiss Re` or `/jobs search pricing`. |
| `/jobs status` | When the scraper last ran, how each source did, and when the next report is due. |
| `/jobs run-now [scrape]` | Make the report now. With `scrape:False` it only posts jobs that are already in the database and haven't been posted yet. *Manage Server.* |
