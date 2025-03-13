# Stage 1: Build environment (slim)
FROM python:3.13.0-slim-bullseye AS builder

# Set timezone
ENV TZ=UTC+2
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Install system dependencies
RUN apt-get update && apt-get install -y netcat libpq5 build-essential libpq-dev curl

# Install tools
RUN pip3 install --progress-bar off --upgrade pip

# Stage 2: Application build (smaller)
FROM python:3.13.0-slim AS app

# Install Pipenv, copy Pipfile and Pipfile.lock for dependency installation
RUN pip3 install --progress-bar off pipenv
COPY Pipfile Pipfile.lock ./

# Install dependencies based on Pipfile
WORKDIR /app
RUN pipenv install --system --deploy

# Copy application code
COPY . .

# Stage 3: Final image (production-ready)
FROM app AS final

# Install development dependencies
RUN pipenv install --dev

# Set up the entrypoint script
COPY docker/backend/entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//g' /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/app/docker/backend/entrypoint.sh"]
