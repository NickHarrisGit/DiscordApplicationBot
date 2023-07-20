# DiscordApplicationBot
A discord bot that will automatically process a google form application for a minecraft server.

# Useage
First, you will need to create a file called .env for your environment variables.
```
SERVER_ID=
STATUS_CHANNEL_ID=
APPLICATIONS_CHANNEL_ID=
BOT_TOKEN=
MINECRAFT_SERVER_IP=
RCON_PASSWORD=
RCON_PORT=
```

Build the Docker container
```docker build -t discordbot .```

Start the Docker container
```docker run -d -p 80:80 --env-file ./.env discordbot```
