#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

# ទាញយក FFmpeg សម្រាប់ប្រើលើ Server
mkdir -p ffmpeg
cd ffmpeg
wget https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz
tar xvf ffmpeg-release-amd64-static.tar.xz --strip-components=1
cd ..