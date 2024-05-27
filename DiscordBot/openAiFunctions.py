from openai import OpenAI

class OpenAIFunctions:
    def __init__(self, api_key):
        self.client = OpenAI(api_key=api_key)

    def detect_subcategory(self, text):
        response = self.client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a content moderation system. Classify each input into one of the following hate speech subcategories: racism, sexism, homophobia, transphobia, xenophobia, or other."},
                {"role": "user", "content": text}
            ],
            model="gpt-3.5-turbo"
        )
        subcategory = response.choices[0].message.content
        return subcategory