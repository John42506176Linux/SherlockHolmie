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