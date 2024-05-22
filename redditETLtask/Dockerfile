FROM python:3.11

# Copy the entire application directory
COPY . /app

# Set the working directory
WORKDIR /app

# Install any dependencies if there's a requirements.txt
RUN pip install -r requirements.txt

# Make downloader.sh executable
RUN chmod +x download.sh

# Command to run the shell script
CMD ["./download.sh"]