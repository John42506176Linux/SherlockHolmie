class GeminiPrompts:
    def __init__(self):
        self.prompts = {
            "batch_insight_prompt": """
            You are a user researcher who wants to help the company by giving
            information and insights based on the following Reddit data
            that help answer the following query: {refined_query}.
            Only give insights on this type of user segment: {user_segment}.
            Please make sure each of your insights are HIGHLY relevant given the following business context: {context}.
            Do not include information that is not directly related to the query.
            If you can make any quantitative judgments, this will highly improve the quality of your report.
            Do not use the same link or quote more than once.
            If you can not find any insights, please state that you could not find any insights. 
            It is better to have no insights than to have irrelevant insights.

            Separate the insights into two separate types:
            - Attitudinal research: Insights based on what users say
            - Behavioral research: Insights based on what users do

            Do not make any conclusions right now; simply present your insights which come directly from the quotes.
            Use a bullet point style:
            1 bullet point for the insight
             - 1 sub bullet point for the point of view the quote likely comes from(state N/A if unsure)
             - 1 sub bullet point for the full link (found in source)
             - 1 sub bullet point for the quote
             - 1 sub bullet point for the time (found in source) in YYYY-MM-DD HH:mm
            
            Every insight should help directly answer the query, do not include tangential information.

            For example:
            Query: "What are the differences in regards to perception of elderly care in different geographies in India?"
            Insight:"Elderly caregivers in Kerala feel that the burden of caring for sick elderly is huge, and that proper institutional mechanisms could prevent financial ruin."


            Here's an example of the format:
            People rely on online learning platforms to gain new skills and advance their careers.

            https://www.reddit.com/r/learnprogramming/comments/qwerty/what_are_the_best_resources_to_learn_coding/
            "I'm trying to switch careers and learn to code. Any recommendations for the best online courses?"
            2023-10-11 13:07
            """
        }

    def add_prompt(self, name, prompt):
        self.prompts[name] = prompt

    def get_prompt(self, name, refined_query=None, user_segment=None, context=None):
        prompt = self.prompts.get(name, "Prompt not found.")
        if refined_query:
            prompt = prompt.replace("{refined_query}", refined_query)
        if user_segment:
            prompt = prompt.replace("{user_segment}", user_segment)
        if context:
            prompt = prompt.replace("{context}", context)
        return prompt

    def remove_prompt(self, name):
        if name in self.prompts:
            del self.prompts[name]
        else:
            return "Prompt not found."

    def list_prompts(self):
        return list(self.prompts.keys())