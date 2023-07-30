# Setup the env.
conda create -n taotie python=3.10
conda activate taotie
# Install the packages.
curl -sSL https://install.python-poetry.org/ | python - || { echo 'Command failed' ; exit 1; }
poetry shell || { echo 'Command failed' ; exit 1; }
poetry install || { echo 'Command failed' ; exit 1; }
pip install -e . || { echo 'Command failed' ; exit 1; }