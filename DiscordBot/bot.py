# bot.py
import discord
from discord.ext import commands
import os
import json
import logging
import re
import requests
from report import Report, State
import pdb
from modReport import ModReport, ModState
from keywords import Keywords
from threePersonReport import ThreePersonReport
from googleapiclient import discovery
from openAiFunctions import OpenAIFunctions
import firebase_admin
from firebase_admin import firestore
from firebase_admin import credentials

# Set up logging to the console
logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

# There should be a file called 'tokens.json' inside the same folder as this file
token_path = 'tokens.json'
if not os.path.isfile(token_path):
    raise Exception(f"{token_path} not found!")
with open(token_path) as f:
    # If you get an error here, it means your token is formatted incorrectly. Did you put it in quotes?
    tokens = json.load(f)
    discord_token = tokens['discord']
    openai_api_key = tokens['openai']


class ModBot(discord.Client):
    def __init__(self): 
        intents = discord.Intents.default()
        intents.message_content = True
        intents.reactions = True
        super().__init__(command_prefix='.', intents=intents)
        self.group_num = None
        self.mod_channels = {} # Map from guild to the mod channel id for that guild
        self.reports = {} # Map from user IDs to the state of their report
        self.mod_reports = {} # Map from moderator IDs to the state of their mod report
        self.three_mod_reports = {} # Map from moderator IDs to the state of their 3 person mod report
        self.user_flag_counts = {} # Map from user IDs to the number of times they've been flagged
        self.three_person_review_team = None # The channel where the three person review team is located
        self.open_ai_functions = OpenAIFunctions(openai_api_key)
        self.keyword_reports = {} # Map from user IDs to the state of their keyword report
        
        # setup firestore
        cred = credentials.Certificate('cs152-a1114-firebase-adminsdk-4hhtt-692136946d.json')
        app = firebase_admin.initialize_app(cred)
        self.db = firestore.client()

    def increment_flag_count(self, user_id):
        # Reference to the user document
        user_ref = self.db.collection('users').document(str(user_id))
        user_doc = user_ref.get()
        
        # Check if the document exists
        if user_doc.exists:
            user_ref.update({'flag_counts': firestore.Increment(1)})
        else:
            user_ref.set({'flag_counts': 1})


    async def on_ready(self):
        print(f'{self.user.name} has connected to Discord! It is these guilds:')
        for guild in self.guilds:
            print(f' - {guild.name}')
        print('Press Ctrl-C to quit.')

        # Parse the group number out of the bot's name
        match = re.search('[gG]roup (\d+) [bB]ot', self.user.name)
        if match:
            self.group_num = match.group(1)
        else:
            raise Exception("Group number not found in bot's name. Name format should be \"Group # Bot\".")

        # Find the mod channel in each guild that this bot should report to
        for guild in self.guilds:
            for channel in guild.text_channels:
                if channel.name == f'group-{self.group_num}-mod':
                    self.mod_channels[guild.id] = channel
                
                if channel.name == f'group-{self.group_num}-3-person-review-team':
                    self.three_person_review_team = channel
        

    async def on_message(self, message):
        '''
        This function is called whenever a message is sent in a channel that the bot can see (including DMs). 
        Currently the bot is configured to only handle messages that are sent over DMs or in your group's "group-#" channel. 
        '''
        # Ignore messages from the bot 
        if message.author.id == self.user.id:
            return

        # Check if this message was sent in a server ("guild") or if it's a DM
        if message.guild:
            await self.handle_channel_message(message)
        else:
            await self.handle_dm(message)

    async def on_raw_reaction_add(self, payload):
        '''
        This function is called whenever a message has a reaction added to it.
        '''
        # Get channel that reaction is in
        channel = self.get_channel(payload.channel_id)
        if channel is None:
            channel = await self.fetch_channel(payload.channel_id)
        
        # Get message that was reacted to
        try:
            message = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            # If the message is not found, possibly deleted
            return
        except discord.Forbidden:
            # The bot does not have permissions to access message
            return
        
        # Only listen for reactions to messages made by the bot
        if message.author.id != self.user.id:
            return
        
        if payload.user_id == self.user.id:
            # ignore reactions premade by the bot
            # print('reaction by bot, ignoring!')
            return

        
        # If reaction is made to a private DM for a user that's currently in reporting flow
        if not payload.guild_id and (payload.user_id in self.reports or payload.user_id in self.keyword_reports):
            if payload.user_id in self.keyword_reports:
                await self.keyword_reports[payload.user_id].handle_reaction(payload, message)
                if self.keyword_reports[payload.user_id].keywords_done():
                    self.keyword_reports.pop(payload.user_id)
            else:
                # Let user report class handle the reaction
                await self.reports[payload.user_id].handle_reaction(payload, message)

                # If the report is complete, forward to mod channel and remove it from our map
                if self.reports[payload.user_id].report_complete():
                    # update the count of times the user has been flagged
                    flagged_user_id = self.reports[payload.user_id].message.author.id

                    # increment the flag count in firestore
                    self.increment_flag_count(flagged_user_id)

                    # increment the flag count in memory for debugging
                    if flagged_user_id in self.user_flag_counts:
                        self.user_flag_counts[flagged_user_id] += 1
                    else:
                        self.user_flag_counts[flagged_user_id] = 1

                    mod_channel = self.mod_channels[self.reports[payload.user_id].message.guild.id]
                    await self.reports[payload.user_id].send_report_to_mod_channel(mod_channel)
                    self.reports.pop(payload.user_id)

                # If the report is cancelled, just remove it from the map
                elif self.reports[payload.user_id].report_cancelled():
                    self.reports.pop(payload.user_id)
        # elif message.channel.name == f'group-{self.group_num}-mod':
        elif not payload.guild_id and payload.user_id in self.mod_reports:
            await self.mod_reports[payload.user_id].handle_reaction(payload, message)

            # if the report is complete or cancelled or was forwarded to the 3 person team, remove it from our map
            if self.mod_reports[payload.user_id].report_complete() or self.mod_reports[payload.user_id].report_in_review_team():
                self.mod_reports.pop(payload.user_id)
        
        elif not payload.guild_id and payload.user_id in self.three_mod_reports:
            await self.three_mod_reports[payload.user_id].handle_reaction(payload, message)

            if self.three_mod_reports[payload.user_id].report_complete():
                self.three_mod_reports.pop(payload.user_id)
        
        return


    async def handle_dm(self, message):
        # Handle a help message
        if message.content == Report.HELP_KEYWORD:
            reply =  "Use the `report` command to begin the reporting process.\n"
            reply += "Use the `cancel` command to cancel the report process.\n"
            reply += "Use the `keywords` command to edit keywords or regular expressions that will trigger a report.\n"
            await message.channel.send(reply)
            return

        author_id = message.author.id
        responses = []

        if author_id in self.keyword_reports:
            await self.keyword_reports[author_id].handle_message(message)
            if self.keyword_reports[author_id].keywords_done():
                self.keyword_reports.pop(author_id)

        # Only respond to messages if they're part of a reporting flow
        if author_id not in self.reports and not (message.content.startswith(Report.START_KEYWORD) or message.content.startswith(Keywords.START_KEYWORD)):
            return

        if message.content.startswith(Keywords.START_KEYWORD):
            if author_id not in self.keyword_reports:
                self.keyword_reports[author_id] = Keywords(self, message.author, self.db)

            await self.keyword_reports[author_id].handle_message(message)
            if self.keyword_reports[author_id].keywords_done():
                self.keyword_reports.pop(author_id)
        else:
            # If we don't currently have an active report for this user, add one
            if author_id not in self.reports:
                self.reports[author_id] = Report(self, message.author)

            # Let the report class handle this message
            await self.reports[author_id].handle_message(message)

            # If the report is complete or cancelled, remove it from our map
            if self.reports[author_id].report_complete():
                mod_channel = self.mod_channels[self.reports[author_id].message.guild.id]
                await self.reports[author_id].send_report_to_mod_channel(mod_channel)
                self.reports.pop(author_id)
            # If the report is cancelled, just remove it from the map
            elif self.reports[author_id].report_cancelled():
                self.reports.pop(author_id)
        
        return

    async def handle_channel_message(self, message):
        # If in group-16 channel, evaluate the message and forward to mod channel if above threshold
        if message.channel.name == f'group-{self.group_num}':
            # first check if there are any keywords that should raise a flag. If so, flag it to mod channel. If not, check for identity attack with perspective API
            keywords_ref = self.db.collection('config').document('keywords')
            keywords_doc = keywords_ref.get()
            keywords_list = []
            if keywords_doc.exists:
                keywords_list = keywords_doc.to_dict().get('keywords_list', [])

            for keyword in keywords_list:
                if keyword.lower() in message.content.lower():
                    await self.send_report_to_mod_channel(message, "Manual Keyword", 1, self.mod_channels[message.guild.id])
                    return

            scores = self.eval_text(message.content)
            identity_attack_score = scores['IDENTITY_ATTACK']
            if identity_attack_score > 0.5:
                subcategory = self.open_ai_functions.detect_subcategory(message.content)
                mod_channel = self.mod_channels[message.guild.id]
                await self.send_report_to_mod_channel(message, subcategory, identity_attack_score, mod_channel)
        elif message.channel.name == f'group-{self.group_num}-mod':
            # This is a message from a moderator in the mod channel
            # Let the ModReport class handle this message
            # If we don't currently have an active report for this user, add one
            author_id = message.author.id
            if author_id not in self.mod_reports:
                self.mod_reports[author_id] = ModReport(self, self.three_person_review_team, self.user_flag_counts, self.db)

            # Let the report class handle this message
            await self.mod_reports[author_id].handle_message(message)

            # If the report is complete or cancelled, remove it from our map
            if self.mod_reports[author_id].report_complete():
                self.mod_reports.pop(author_id)


            # mod_report = ModReport(self)
            # await mod_report.handle_message(message)
            # self.mod_reports[message.author.id] = mod_report
        # mod message in 3 person team channel
        elif message.channel.name == f'group-{self.group_num}-3-person-review-team':
            author_id = message.author.id
            if author_id not in self.three_mod_reports:
                self.three_mod_reports[author_id] = ThreePersonReport(self, self.three_person_review_team)

            await self.three_mod_reports[author_id].handle_message(message)

            if self.three_mod_reports[author_id].report_complete():
                self.three_mod_reports.pop(author_id)

    
    def eval_text(self, message):
        ''''
        TODO: Once you know how you want to evaluate messages in your channel, 
        insert your code here! This will primarily be used in Milestone 3. 
        '''
        api_key = tokens['perspective']  # Make sure your 'tokens.json' file includes the Perspective API key
        client = discovery.build(
            "commentanalyzer",
            "v1alpha1",
            developerKey=api_key,
            discoveryServiceUrl="https://commentanalyzer.googleapis.com/$discovery/rest?version=v1alpha1",
            static_discovery=False,
        )

        analyze_request = {
            'comment': {'text': message},
            'requestedAttributes': {
                'TOXICITY': {},
                'SEVERE_TOXICITY': {},
                'IDENTITY_ATTACK': {}
            }
        }

        response = client.comments().analyze(body=analyze_request).execute()

        scores = {
            'TOXICITY': response['attributeScores']['TOXICITY']['summaryScore']['value'],
            'SEVERE_TOXICITY': response['attributeScores']['SEVERE_TOXICITY']['summaryScore']['value'],
            'IDENTITY_ATTACK': response['attributeScores']['IDENTITY_ATTACK']['summaryScore']['value']
        }
        return scores

    
    def code_format(self, text):
        ''''
        TODO: Once you know how you want to show that a message has been 
        evaluated, insert your code here for formatting the string to be 
        shown in the mod channel. 
        '''
        return "Evaluated: '" + text+ "'"
    
    async def send_report_to_mod_channel(self, message, subcategory, score, mod_channel):
        priority = "Low"
        if score > 0.7:
            priority = "Medium"
        if score > 0.9:
            priority = "High"
        
        color_dict = {
            "Low": discord.Color.blue(),
            "Medium": discord.Color.gold(),
            "High": discord.Color.red()
        }
        color = color_dict.get(priority, discord.Color.default())

        embed = discord.Embed(
            title="New Report Filed",
            description=f"The following message was automatically flagged for review:",
            color=color
        )
        embed.add_field(name="Message Content", value=f"```{message.author.name}: {message.content}```", inline=False)
        embed.add_field(name="Priority", value=priority, inline=True)
        embed.add_field(name="Identity Attack Score", value=score, inline=True)
        embed.add_field(name="Subcategory:", value=subcategory, inline=False)

        await mod_channel.send(embed=embed)


client = ModBot()
client.run(discord_token)