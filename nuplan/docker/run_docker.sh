CURRENT_PATH="$PWD"

docker run --name aleksey_nuplan --privileged --rm --gpus all -it -p 8888:8888\
      -v /mnt/hdd5/NuPlan/dockerfiles/dataset:/nuplan-devkit/nuplan/dataset:rw \
      aleksey/nuplan
