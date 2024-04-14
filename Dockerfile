# Use the official Python 3.11 slim image as the base
FROM python:3.11-slim

# Set the working directory to /app in the container
WORKDIR /app

# Copy the requirements.txt file from the host into the /app directory in the container
COPY requirements.txt /app

# Create a .cache directory at the root (/) of the container and set permissions to allow all users
RUN mkdir /.cache && chmod 777 /.cache

# Install Python dependencies listed in requirements.txt using pip
RUN pip install -r requirements.txt

# Copy the entire current directory from the host into the /app directory in the container
COPY . /app

# Expose port 23333 to allow communication with services outside the container
EXPOSE 23333

# Set the default command to run the 'chat_api' module of your application using Python
CMD ["python", "-m", "apis.chat_api"]
