import requests

# Define the URL of the endpoint
url = 'http://localhost:3000/api/tasks'

# Define the data to be sent in the body of the POST request
data = {
    'requestId': 'some_value',  # Replace 'some_value' with the actual value you want to test
    'result': 'another_value'   # Replace 'another_value' with the actual value you want to test
}

# Send the POST request
response = requests.post(url, json=data)

# Print the response status code and JSON body
print(f"Status Code: {response.status_code}")
print(f"Response JSON: {response.json()}")
