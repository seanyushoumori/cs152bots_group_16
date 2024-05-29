from enum import Enum, auto
import discord
import re

class KeywordState(Enum):
    START_KEYWORDS = auto()
    CANCELLED_KEYWORDS = auto()
    AWAITING_KEYWORDS = auto()
    LIST_KEYWORDS = auto()
    ADD_KEYWORD = auto()
    REMOVE_KEYWORD = auto()

class Keywords:
    START_KEYWORD = "keywords"
    # LIST_KEYWORD = "list keywords"
    # ADD_KEYWORD = "add keyword"
    # REMOVE_KEYWORD = "remove keyword"
    CANCEL_KEYWORD = "cancel"

    def __init__(self, client, reporter, db):
        self.reporter = reporter
        self.state = KeywordState.START_KEYWORDS
        self.client = client
        self.message = None
        self.final_state = None
        self.db = db
    
    async def handle_message(self, message):
        '''
        This function makes up the meat of the user-side reporting flow. It defines how we transition between states and what 
        prompts to offer at each of those states. You're welcome to change anything you want; this skeleton is just here to
        get you started and give you a model for working with Discord. 
        '''
        print('handling message')

        if message.content == self.CANCEL_KEYWORD:
            self.state = KeywordState.CANCELLED_KEYWORDS
            await message.channel.send("Keyword edit cancelled.")
            return
        
        if self.state == KeywordState.START_KEYWORDS:
            reply =  "Thank you for starting the keyword editing process. "
            # reply += "Please type `add keyword` to add a keyword, `remove keyword` to remove a keyword, or `list keywords` to see all keywords."
            reply += "Please react with a corresponding number for the action you'd like to take.\n"
            reply += "1️⃣ - List Keywords\n"
            reply += "2️⃣ - Add Keyword\n"
            reply += "3️⃣ - Remove Keyword\n"
            reply += "4️⃣ - Done/Cancel"
            
            self.state = KeywordState.AWAITING_KEYWORDS
            sent_message = await message.channel.send(reply)
            self.abuse_category_message_id = sent_message.id
            return
        
        if self.state == KeywordState.ADD_KEYWORD:
            print('adding keyword')
            keywords_ref = self.db.collection('config').document('keywords')
            keywords_doc = keywords_ref.get()
            if keywords_doc.exists:
                keywords_list = keywords_doc.to_dict().get('keywords_list', [])
            else:
                keywords_list = []
            
            if message.content in keywords_list:
                sent_message = await message.channel.send("Keyword already exists.")
                self.state = KeywordState.START_KEYWORDS
                await self.handle_message(sent_message)
                return
            
            keywords_list.append(message.content)
            keywords_ref.set({
                'keywords_list': keywords_list
            })

            sent_message = await message.channel.send("Keyword added successfully.")
            self.state = KeywordState.START_KEYWORDS
            await self.handle_message(sent_message)
            return
        
        if self.state == KeywordState.REMOVE_KEYWORD:
            print('removing keyword')
            keywords_ref = self.db.collection('config').document('keywords')
            keywords_doc = keywords_ref.get()
            if keywords_doc.exists:
                keywords_list = keywords_doc.to_dict().get('keywords_list', [])
            else:
                keywords_list = []
            
            if message.content not in keywords_list:
                sent_message = await message.channel.send("Keyword does not exist.")
                self.state = KeywordState.START_KEYWORDS
                await self.handle_message(sent_message)
                return
            
            keywords_list.remove(message.content)
            keywords_ref.set({
                'keywords_list': keywords_list
            })

            sent_message = await message.channel.send("Keyword removed successfully.")
            self.state = KeywordState.START_KEYWORDS
            await self.handle_message(sent_message)
            return
        
        # if self.state == KeywordState.AWAITING_KEYWORDS:
        #     # Parse out the three ID strings from the message link
        #     # m = re.search('/(\d+)/(\d+)/(\d+)', message.content)
        #     # if not m:
        #     #     await message.channel.send("I'm sorry, I couldn't read that link. Please try again or say `cancel` to cancel.")
        #     #     return
        #     # guild = self.client.get_guild(int(m.group(1)))
        #     # if not guild:
        #     #     await message.channel.send("I cannot accept reports of messages from guilds that I'm not in. Please have the guild owner add me to the guild and try again.")
        #     #     return
        #     # channel = guild.get_channel(int(m.group(2)))
        #     # if not channel:
        #     #     await message.channel.send("It seems this channel was deleted or never existed. Please try again or say `cancel` to cancel.")
        #     #     return
        #     # try:
        #     #     self.message = await channel.fetch_message(int(m.group(3)))
        #     # except discord.errors.NotFound:
        #     #     await message.channel.send("It seems this message was deleted or never existed. Please try again or say `cancel` to cancel.")
        #     #     return

        #     # Here we've found the message - it's up to you to decide what to do next!
        #     self.state = State.MESSAGE_IDENTIFIED
        #     sent_message = await message.channel.send(
        #         f"I found this message:\n"
        #         f"```{self.message.author.name}: {self.message.content}```\n"
        #         "Please react with the corresponding number for the reason of your report:\n"
        #         "1️⃣ - Harassment\n"
        #         "2️⃣ - Offensive Content\n"
        #         "3️⃣ - Urgent Violence\n"
        #         "4️⃣ - Others/I don't like this")
        #     self.abuse_category_message_id = sent_message.id
        #     return
        
        # if self.state == State.OTHERS_CHOSEN:
        #     # TODO: Save this message somehow
        #     self.other_explanation = message.content
        #     self.final_state = "Others/I don't like this"

        #     self.state = State.BLOCK_USER
        #     sent_message = await message.channel.send(
        #         "Thank you for your report. Would you like to block this user?\n"
        #         "If so, please react to this message with 👍.\n"
        #         "Otherwise, react to this message with 👎."
        #     )
        #     self.block_user_message_id = sent_message.id
        #     return
        
        return
    
    async def handle_reaction(self, payload, message):
        if self.state == KeywordState.AWAITING_KEYWORDS:
            if payload.message_id != self.abuse_category_message_id:
                await message.channel.send("Please react to the message that contains emoji options to choose from.")
                return
            
            if str(payload.emoji) == '1️⃣':
                # self.state = KeywordState.LIST_KEYWORDS
                # sent_message = await message.channel.send(
                #     "Please react with the corresponding number for which type of harassment you're reporting:\n"
                #     "1️⃣ - Trolling\n"
                #     "2️⃣ - Impersonation\n"
                #     "3️⃣ - Directed Hate Speech\n"
                #     "4️⃣ - Doxing\n"
                #     "5️⃣ - Unwanted Sexual Content\n")
                # self.harassment_type_message_id = sent_message.id
                keywords_ref = self.db.collection('config').document('keywords')
                keywords_doc = keywords_ref.get()
                sentMessage = None
                if keywords_doc.exists:
                    keywords_list = keywords_doc.to_dict().get('keywords_list', [])
                    sent_message = await message.channel.send("Here are the current keywords: \n" + "\n".join(keywords_list))
                else:
                    sent_message = await message.channel.send("There are no keywords currently.")

                self.state = KeywordState.START_KEYWORDS
                await self.handle_message(sent_message)

                return
            elif str(payload.emoji) == '2️⃣':
                # adding keyword
                await message.channel.send("Please write the keyword you'd like to add.")
                self.state = KeywordState.ADD_KEYWORD
                return
            elif str(payload.emoji) == '3️⃣':
                await message.channel.send("Please write the keyword you'd like to remove.")
                self.state = KeywordState.REMOVE_KEYWORD
                return
            elif str(payload.emoji) == '4️⃣':
                # done/cancel
                self.state = KeywordState.CANCELLED_KEYWORDS
                await message.channel.send("Ending the keyword editing process.")
                return
            
            await message.channel.send("Sorry, I don't understand what you mean by this emoji. Please react to the previous message with either 1️⃣, 2️⃣, 3️⃣, or 4️⃣")
            return
        
        return
    
    # async def send_report_to_mod_channel(self, mod_channel):
    #     if self.state != State.REPORT_COMPLETE:
    #         return

    #     color_dict = {
    #         PriorityLevel.LOW: discord.Color.blue(),
    #         PriorityLevel.MEDIUM: discord.Color.gold(),
    #         PriorityLevel.HIGH: discord.Color.red()
    #     }
    #     color = color_dict.get(self.priority_level, discord.Color.default())

    #     embed = discord.Embed(
    #         title="New Report Filed",
    #         description=f"User {self.reporter.name} filed a report against the following message:",
    #         color=color
    #     )
    #     embed.add_field(name="Message Content", value=f"```{self.message.author.name}: {self.message.content}```", inline=False)
    #     embed.add_field(name="Priority", value=self.priority_level.value, inline=True)
    #     embed.add_field(name="Reported by", value=self.reporter.name, inline=True)
    #     embed.add_field(name="Reported abuse type", value=self.final_state, inline=False)
    #     if self.other_explanation:
    #         embed.add_field(name="User explanation", value=self.other_explanation, inline=False)

    #     await mod_channel.send(embed=embed)


    # def keywords_complete(self):
    #     return self.state == State.REPORT_COMPLETE
    
    def keywords_done(self):
        return self.state == KeywordState.CANCELLED_KEYWORDS
    


    

