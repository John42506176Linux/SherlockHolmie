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
RUN chmod +x startup.sh

# Use the startup script as the command to run when the container starts
CMD ["/bin/sh", "startup.sh"]