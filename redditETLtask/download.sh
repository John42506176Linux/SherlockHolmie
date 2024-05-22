#!/bin/bash

# Run downloader.py
echo "Running downloader.py..."
python3 downloader.py

# Check if downloader.py executed successfully
if [ $? -ne 0 ]; then
  echo "Error running downloader.py"
  exit 1
fi

# Run embedder.py only if downloader.py was successful
echo "Running embedder.py..."
python3 embedder.py

# Check if embedder.py executed successfully
if [ $? -ne 0 ]; then
  echo "Error running embedder.py"
  exit 1
fi

echo "Both scripts ran successfully."
