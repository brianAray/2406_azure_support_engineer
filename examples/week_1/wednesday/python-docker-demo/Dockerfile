# Step 1: Use an official lightweight Python image
FROM python:3.11-slim

# Step 2: Set the working directory inside the container
WORKDIR /app

# Step 3: Copy our local app file into the container's working directory
COPY app.py .

# Step 4: Expose the port our app runs on for the container
EXPOSE 8081

# Step 5: Define the command to run the application
CMD ["python", "app.py"]