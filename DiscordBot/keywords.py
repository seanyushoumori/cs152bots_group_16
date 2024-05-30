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
        self.reactions = ['1️⃣', '2️⃣', '3️⃣', '4️⃣']
    
    async def handle_message(self, message):
        '''
        This function makes up the meat of the user-side reporting flow. It defines how we transition between states and what 
        prompts to offer at each of those states. You're welcome to change anything you want; this skeleton is just here to
        get you started and give you a model for working with Discord. 
        '''

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

            # preadd the reactions so it's easy for the user to click
            
            for reaction in self.reactions:
                await sent_message.add_reaction(reaction)

            return
        
        if self.state == KeywordState.ADD_KEYWORD:
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
        
        return
    
    async def handle_reaction(self, payload, message):
        if self.state == KeywordState.AWAITING_KEYWORDS:
            if payload.message_id != self.abuse_category_message_id:
                await message.channel.send("Please react to the message that contains emoji options to choose from.")
                return
            
            if str(payload.emoji) == '1️⃣':
                keywords_ref = self.db.collection('config').document('keywords')
                keywords_doc = keywords_ref.get()
                sentMessage = None
                if keywords_doc.exists:
                    keywords_list = keywords_doc.to_dict().get('keywords_list', [])
                    sent_message = await message.channel.send("Here are the current keywords: ```\n" + "\n".join(keywords_list) + "\n```")
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
    
    def keywords_done(self):
        return self.state == KeywordState.CANCELLED_KEYWORDS
    


    

