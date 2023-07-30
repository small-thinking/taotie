# Setup the env.
conda create -n taotie python=3.10
conda activate taotie
# Install the packages.
pip install poetry
poetry shell
poetry install
source $HOME/.poetry/env