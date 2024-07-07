import json
import re
import logging.handlers


# TODO: Set up full logging
log = logging.getLogger("bot")
log.setLevel(logging.DEBUG)

def escape_quotes_in_json(json_string):
    # Use a regular expression to find non-escaped quotes within JSON data
    escaped_string = re.sub(r'(?<!\\)"', r'\"', json_string)
    return escaped_string

def get_json_from_output(input_string):
    # Extract JSON data between <json> tags
    json_data_match = re.search(r'<json>(.*?)</json>', input_string, re.DOTALL)
    if json_data_match:
        json_data_str = json_data_match.group(1).strip()
        # Preprocess JSON data to escape problematic double quotes        
        # Parse the JSON data
        try:
            json_data = json.loads(json_data_str)
            if "PainPoints" in json_data:
                return json_data["PainPoints"]
            else:
                print(f"Errored Json:{json_data}")
                print("Key 'PainPoints' not found in JSON data.")
                return {}
        except Exception as e:
            print(f"Failed to decode JSON: {e}")
            print(f"Problematic JSON data: {json_data_str}...")
            return {}
    else:
        print("No JSON data found between <json> tags.")
    return {}

def extract_post_title_from_permalink(permalink):
    # Use regular expression to extract the descriptive part of the title
    match = re.search(r'/comments/[^/]+/([^/]+)/', permalink)
    if match:
        # Replace underscores with spaces
        title_with_spaces = match.group(1).replace('_', ' ')
        return title_with_spaces
    return None

EMOTION_VALUES = {
    "Joy": 1.0,
    "Trust": 0.8,
    "Gratitude": 0.8,
    "Excitement": 0.8,
    "Admiration": 0.7,
    "Relief": 0.7,
    "Satisfaction": 0.7,
    "Hope": 0.6,
    "Optimism": 0.6,
    "Pride": 0.6,
    "Curiosity": 0.5,
    "Anticipation": 0.5,
    "Sympathy": 0.4,
    "Surprise": 0.4,
    "Neutral": 0.0,
    "Concern": -0.3,
    "Skepticism": -0.4,
    "Confusion": -0.4,
    "Embarrassment": -0.4,
    "Apprehension": -0.5,
    "Frustration": -0.5,
    "Envy": -0.5,
    "Wariness": -0.3,
    "Sadness": -0.5,
    "Worry": -0.3,
    "Disappointment": -0.6,
    "Boredom": -0.3,
    "Resentment": -0.7,
    "Distrust": -0.7,
    "Anxiety": -0.3,
    "Fear": -0.8,
    "Disgust": -0.9,
    "Anger": -0.9
}