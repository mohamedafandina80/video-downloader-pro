#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

# تحميل ffmpeg بشكل محلي للسيرفر
mkdir -p ffmpeg
curl -L https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz | tar xJ -C ffmpeg --strip-components 1
export PATH=$PATH:$(pwd)/ffmpeg