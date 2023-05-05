# Pull base image
FROM python:3.10.2-slim-bullseye

# Set environment variables
ENV PIP_DISABLE_PIP_VERSION_CHECK 1
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
RUN mkdir -p /app/
WORKDIR /app

# Install dependencies
COPY ./requirements.txt .
RUN pip3 install --upgrade pip
RUN pip install -r requirements.txt

# Copy project
COPY . .