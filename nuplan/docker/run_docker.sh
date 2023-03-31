CURRENT_PATH="$PWD"


# jupyter 8888
# tensorboard 6006
# nuplan board 5006
docker run --name nuplan --privileged --gpus all -it -p 8888:8888 -p 6006:6006 -p 5006:5006\
      -v ~/lab_work_space/nuScenes/nuplan_repo/datasets:/nuplan-devkit/nuplan/dataset:rw \nuplan