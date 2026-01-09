#!/usr/bin/env bash
# Установка библиотек Python
pip install -r requirements.txt

# Скачивание самого движка для видео (yt-dlp)
mkdir -p bin
curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o bin/yt-dlp
chmod a+rx bin/yt-dlp

# Установка ffmpeg (нужен для склейки видео и звука)
# На Render это делается через установку в локальную папку или использование статических бинарников

