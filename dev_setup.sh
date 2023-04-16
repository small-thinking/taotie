python3 -m venv taotie
source taotie/bin/activate  # On Windows, use "taotie\Scripts\activate"

# Install the packages.
pip3 install --upgrade pip
pip3 install poetry
poetry shell
poetry install