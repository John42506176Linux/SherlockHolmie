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
                log.error(f"Errored Json:{json_data}")
                return None
        except Exception as e:
            log.error(f"Failed to decode JSON: {e}")
    return None