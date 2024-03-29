#!/usr/bin/env bash

docker run \
  --gpus all \
  --shm-size=1g \
  --ulimit memlock=-1 \
  --ulimit stack=67108864 \
  --rm \
  -v /space/code/deep-learning:/workspace/deep-learning \
  -v /space/code/keras-maskrcnn:/workspace/keras-maskrcnn \
  -p 8888:8888 \
  -it \
  deep-learning "$@"
