FROM python:3.11

# Copy the entire application directory
COPY . /app

# Set the working directory
WORKDIR /app

# Install any needed packages specified in requirements.txt
RUN pip install -r requirements.txt

# Make port 80 available to the world outside this container
EXPOSE 80

# Run fts_query.py when the container launches
CMD ["uvicorn", "tasks.reportTask.main:app", "--host", "0.0.0.0", "--port", "80"]