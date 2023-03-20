conda activate nuplan
conda env create -f environment.yml && pip install -e .
pip install -r requirements_torch.txt
pip install -r requirements.txt
pip install jupyter
apt-get update && apt-get install ffmpeg libsm6 libxext6  -y
export NUPLAN_DATA_ROOT="/nuplan-devkit/nuplan/dataset"
export NUPLAN_MAPS_ROOT="/nuplan-devkit/nuplan/dataset/maps"
export NUPLAN_EXP_ROOT="/nuplan-devkit/nuplan/exp"

