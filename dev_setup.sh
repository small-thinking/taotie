# Setup the env.
conda create -n taotie python=3.10
conda activate taotie
# Install the packages.
curl -sSL https://install.python-poetry.org/ | python -
poetry shell
poetry install
pip install -e .