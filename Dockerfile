FROM python:3.12-slim

WORKDIR /app

# Install all required dependencies
RUN pip install --no-cache-dir discord.py flask pyyaml python-dotenv

# Copy your project files
COPY . .

CMD ["python", "main.py"]