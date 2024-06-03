class OpenAIPrompts:
    def __init__(self):
        self.prompts = {
            "summarize_insights_json_prompt": """
            You are an entrepreneur who wants to ask the following question: {refined_query}
            About the following space: {space}

            A team of user researchers has collected various insights from Reddit data to help you answer this question. The data is separated into two types:
            - Attitudinal Research: Insights based on what users say
            - Behavioral Research: Insights based on what users do

            Use the data given to make a final conclusive list of insights to answer the query. If you can make any quantitative judgments, this will highly improve the quality of your report. 

            DO NOT USE THE SAME LINK OR QUOTE MORE THAN ONCE.

            Make a clear definitive conclusion based on the research. You may use your own judgment based on the data, but be conclusive.

            Return the information in a JSON format like the following example:

            {{
              "researchInsights": {{
                "attitudinal": [
                  {{
                    "insight": "Insight description goes here.",
                    "source": "https://www.example.com/attitudinal/source1",
                    "quote": "Example quote related to the insight goes here.",
                    "date": "YYYY-MM-DDTHH:MM:SSZ"
                  }},
                  {{
                    "insight": "Another insight description goes here.",
                    "source": "https://www.example.com/attitudinal/source2",
                    "quote": "Another example quote related to the insight goes here.",
                    "date": "YYYY-MM-DDTHH:MM:SSZ"
                  }}
                ],
                "behavioral": [
                  {{
                    "insight": "Behavioral insight description goes here.",
                    "source": "https://www.example.com/behavioral/source1",
                    "quote": "Example quote related to the behavioral insight goes here.",
                    "date": "YYYY-MM-DDTHH:MM:SSZ"
                  }},
                  {{
                    "insight": "Another behavioral insight description goes here.",
                    "source": "https://www.example.com/behavioral/source2",
                    "quote": "Another example quote related to the behavioral insight goes here.",
                    "date": "YYYY-MM-DDTHH:MM:SSZ"
                  }}
                ]
              }},
              "conclusion": "Conclusion based on the attitudinal and behavioral research insights goes here.",
              "userSegments": [
                {{
                  "segment": "Segment name goes here",
                  "description": "Description of this user segment goes here."
                }},
                {{
                  "segment": "Another segment name goes here",
                  "description": "Description of another user segment goes here."
                }}
              ]
            }}
            """
        }

    def add_prompt(self, name, prompt):
        self.prompts[name] = prompt

    def get_prompt(self, name, refined_query=None, space=None):
        prompt = self.prompts.get(name, "Prompt not found.")
        if refined_query and "{refined_query}" in prompt:
            prompt = prompt.replace("{refined_query}", refined_query)
        if space and "{space}" in prompt:
            prompt = prompt.replace("{space}", space)
        return prompt

    def remove_prompt(self, name):
        if name in self.prompts:
            del self.prompts[name]
        else:
            return "Prompt not found."

    def list_prompts(self):
        return list(self.prompts.keys())