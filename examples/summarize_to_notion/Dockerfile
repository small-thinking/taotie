FROM python:3.10-bullseye

# Install system dependencies
RUN apt-get update --allow-releaseinfo-change && apt-get install -y \
        build-essential \
        cargo \
        coreutils \
        gcc \
        gettext \
        libcairo2-dev \
        libffi-dev \
        libfreetype6-dev \
        libgdk-pixbuf2.0-dev \
        libjpeg-dev \
        liblcms2-dev \
        libopenjp2-7-dev \
        libpango1.0-dev \
        libpq-dev \
        libssl-dev \
        libtiff5-dev \
        musl-dev \
        poppler-utils \
        postgresql-client \
        python3-dev \
        tcl-dev \
        tk-dev \
        fonts-noto-cjk \
        zlib1g-dev \
        wget \
        unzip

ENV PATH="${PATH}:/usr/local/bin"
ENV IS_DOCKER=true

# Copy the project files into the container
WORKDIR /app
COPY .env .
COPY . .

# Expose port 6543
EXPOSE 6543

# Upgrade pip, install Poetry, and install project dependencies using Poetry
RUN pip install --upgrade pip \
    && curl -sSL https://install.python-poetry.org/ | python - \
    && poetry export --without-hashes -f requirements.txt > requirements.txt \
    && pip3 install -r requirements.txt \
    && pip3 install cryptography \
    && pip3 install -e .
# Start the application
CMD ["python", "examples/summarize_to_notion/example.py"]
