import discord
from discord.ext import commands, tasks
import sqlite3
import time
import datetime
import asyncio
import mcrcon

# Define the application duration in seconds
APPLICATION_DURATION_SECONDS = 60*60*24*2  # 2 days  

class ApplicationBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Connect to the SQLite database
        self.conn = sqlite3.connect('applications.db')

        # Create a cursor
        self.cursor = self.conn.cursor()

        # Create table if it doesn't already exist
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                username TEXT,
                full_name TEXT,
                email TEXT,
                minecraft_username TEXT,
                why_join TEXT,
                favorite_aspect TEXT,
                youtube_channel TEXT,
                twitch_channel TEXT,
                thread_id INTEGER,
                vote_message_id INTEGER,
                application_message_id INTEGER,
                expiry_time REAL,
                thumbs_up INTEGER,
                thumbs_down INTEGER,
                result TEXT
            )
        """)
        # Set self.guild_id
        with open("server.id", 'r') as f:
            self.guild_id = int(f.read().strip())
    
    async def log_to_channel(self, message):
        # Read the channel ID from the file
        with open("status_channel.id", 'r') as f:
            status_channel_id = int(f.read().strip())

        # Fetch the channel
        status_channel = self.get_channel(status_channel_id)

        # Send the message to the channel
        await status_channel.send(message)

    async def on_ready(self):
        print(f'We have logged in as {self.user}')
        await self.log_to_channel(f'Logged in as {self.user}')
        
        # Start the vote timer task
        self.vote_timer.start()

    async def on_message(self, message):
        if message.author == self.user:
            return

        if message.channel.name == 'applications':
            print("Detected a form submission.")
            await self.log_to_channel("Detected a form submission.")
            await asyncio.sleep(5)  # Increase delay from 1 second to 5 seconds
            message = await message.channel.fetch_message(message.id)  # Fetch the message again
            if message.embeds:
                print("Embeds:")
                for embed in message.embeds:
                    print(embed.to_dict())
            else:
                print("No embeds in the message.")
                await self.log_to_channel("No embeds in the message.")
            await self.process_application(message)

    async def process_application(self, message):
        embed = message.embeds[0].to_dict()  # Convert the Embed object to a dictionary
        fields = embed['fields']  # Get the fields from the embed

        # Extract values of all fields
        username = fields[0]['value']
        full_name = fields[1]['value']
        email = fields[2]['value']
        minecraft_username = fields[3]['value']
        why_join = fields[4]['value']
        favorite_aspect = fields[5]['value']

        # Extract YouTube and Twitch channel links if they exist
        youtube_channel = fields[6]['value'] if len(fields) > 6 and fields[6]['value'] != "" else None
        twitch_channel = fields[7]['value'] if len(fields) > 7 and fields[7]['value'] != "" else None

        print(f"Extracted username: {username}")
        await self.log_to_channel("Extracted username: {username}")

        applications_channel = discord.utils.get(message.guild.text_channels, name='applications')
        user = await self.fetch_user(int(username))
        human_readable_username = user.name
        thread = await applications_channel.create_thread(name=f'{human_readable_username} Application Discussion')
        self.guild_id = message.guild.id

        ir_team_role = discord.utils.get(message.guild.roles, name="temptest")
        vote_message = await thread.send(f'{ir_team_role.mention} New application for review by {human_readable_username}.')  # Save the returned Message object

        await vote_message.add_reaction("👍")  # Add reactions to the new message in the thread
        await vote_message.add_reaction("👎")

        # Calculate the expiry time for the application
        expiry_time = time.time() + APPLICATION_DURATION_SECONDS
        print(f"Current time: {time.time()}, Expiry time: {expiry_time}")  # Debug line to print current and expiry time
        await self.log_to_channel("Current time: {time.time()}, Expiry time: {expiry_time}")

        # Insert the application data into the database
        self.cursor.execute("""
            INSERT INTO applications VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL)
        """, (username, full_name, email, minecraft_username, why_join, favorite_aspect, youtube_channel, twitch_channel, thread.id, vote_message.id, message.id, expiry_time))  # Save the ID of the new message

        # Commit the changes
        self.conn.commit()

    @tasks.loop(seconds=300) # Run the task every 5 minutes
    async def vote_timer(self):
        
        user = None
        human_readable_username = None
        guild = await bot.fetch_guild(self.guild_id)
        print("Vote timer tick...")
        await self.log_to_channel("Vote timer tick...")
        # Fetch all applications from the database
        self.cursor.execute("""
            SELECT * FROM applications
        """)
        all_applications = self.cursor.fetchall()

        print(f"Found {len(all_applications)} applications.")
        await self.log_to_channel(f"Found {len(all_applications)} applications.")

        # Process each application
        for application in all_applications:
            print(f"Processing application {application[0]}...")
            await self.log_to_channel(f"Processing application {application[0]}...")
            username, full_name, email, minecraft_username, why_join, favorite_aspect, youtube_channel, twitch_channel, thread_id, vote_message_id, application_message_id, expiry_time, _, _, _ = application
            member = await guild.fetch_member(int(username))

            if datetime.datetime.utcnow().timestamp() < expiry_time - 5:  # Subtract 5 seconds as a buffer
                print(f"Application {username} is not expired yet.")
                await self.log_to_channel("Application {username} is not expired yet.")
                continue

            print(f"Application {username} expired. Tallying votes...")
            await self.log_to_channel(f"Application {username} expired. Tallying votes...")
            thread = self.get_channel(thread_id)
            if thread is None:
                print(f"Thread {thread_id} not found.")
                await self.log_to_channel(f"Thread {thread_id} not found.")
                continue
            print(f"Thread {thread.name} found, with id {thread.id} and type {thread.type}.")
            await self.log_to_channel(f"Thread {thread.name} found, with id {thread.id} and type {thread.type}.")
            try:
                vote_message = await thread.fetch_message(vote_message_id)
            except discord.errors.NotFound:
                print(f"Vote message {vote_message_id} not found.")
                await self.log_to_channel(f"Vote message {vote_message_id} not found.")
                continue

            thumbs_up = 0
            thumbs_down = 0

            # Count the votes
            for reaction in vote_message.reactions:
                if reaction.emoji == "👍":
                    thumbs_up = reaction.count - 1
                elif reaction.emoji == "👎":
                    thumbs_down = reaction.count - 1

            # Decide the result based on the vote counts
            if thumbs_up > thumbs_down:
                result = "approved"
            else:
                result = "denied"

            print(f"Votes for {human_readable_username}: 👍 {thumbs_up}, 👎 {thumbs_down}. Result: {result.capitalize()}.")
            await self.log_to_channel(f"Votes for {human_readable_username}: 👍 {thumbs_up}, 👎 {thumbs_down}. Result: {result.capitalize()}.")

            # Update the database with the vote counts and result
            self.cursor.execute("""
                UPDATE applications
                SET thumbs_up = ?, thumbs_down = ?, result = ?
                WHERE username = ?
            """, (thumbs_up, thumbs_down, result, username))

            # Commit the changes
            self.conn.commit()

            # Try to fetch the user
            user = await self.fetch_user(int(username))

            # If denied, reject the application
            if result == "denied":
                print(f"User {username} is denied.")
                await self.log_to_channel("User {username} is denied.")
                # Send a DM to the applicant, informing them of the decision
                if user is not None:
                    await user.send(f"Your application for the Infinite Realms Minecraft Server has been {result} based on the votes from the current users.")
            
            # If approved, accept the application
            if result == "approved":
                print(f"User {username} is approved.")
                await self.log_to_channel(f"User {username} is approved.")
                if user is not None:
                    await user.send(f"Congratulations! Your application for the Infinite Realms Minecraft Server has been {result} based on the votes from the current users. Now you will have the IR Team role and you will be automatically whitelisted on the Minecraft Server.")
                # Assign the Discord role "IR Team" to the user
                ir_team_role = discord.utils.get(guild.roles, name="IR Team")
                await member.add_roles(ir_team_role)

                # Add the user to the Minecraft Server whitelist
                # This part depends on how you manage your Minecraft Server. You might need to use RCON or SSH to send commands to the server.
                # For example, if you're using a RCON library, you can do:
                rcon = mcrcon.MCRcon(host="192.168.1.138", port=25575, password="TemporaryTestPasswordThatIsSuperSecure12345%$#")
                rcon.connect()
                rcon.command(f"/whitelist add {minecraft_username}")
                rcon.disconnect()

            # Try to delete the application message and the thread
            await asyncio.sleep(5)  # Increase delay from 1 second to 5 seconds
            try:
                with open("application.id", "r") as f:
                    APPLICATIONS_CHANNEL_ID = int(f.read().strip())
                applications_channel = self.get_channel(APPLICATIONS_CHANNEL_ID)
                print(f"applications_channel: {applications_channel}")
                await self.log_to_channel("applications_channel: {applications_channel}")
                application_message = await applications_channel.fetch_message(application_message_id)
                print(f"Application message {application_message.content} found, with id {application_message.id}.")
                await self.log_to_channel(f"Application message {application_message.content} found, with id {application_message.id}.")
                await application_message.delete()
                print(f"Application message {application_message.content} found, with id {application_message.id}.")
                await self.log_to_channel(f"Application message {application_message.content} found, with id {application_message.id}.")
                await application_message.delete()
            except discord.errors.NotFound:
                print(f"Application message {application_message_id} not found.")
                await self.log_to_channel(f"Application message {application_message_id} not found.")
            await asyncio.sleep(5)  # Increase delay from 1 second to 5 seconds
            try:
                await thread.delete()
            except discord.errors.NotFound:
                print(f"Thread {thread_id} not found.")
                await self.log_to_channel(f"Thread {thread_id} not found.")

            # Delete the application from the database
            self.cursor.execute("DELETE FROM applications WHERE username = ?", (username,))
            
            # Commit the changes
            self.conn.commit()

    async def close(self):
        await super().close()
        self.conn.close()

# Define the bot's intents (what events it can receive)
intents = discord.Intents.all()

with open("bot.token", 'r') as f:
    token = f.read().strip()

bot = ApplicationBot(intents=intents, command_prefix="!")

bot.run(token)