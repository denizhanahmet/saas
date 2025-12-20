@echo off
REM Tailwind CSS'i otomatik olarak yükle ve derle
REM 1. tailwindcss'i yükle
npm install -D tailwindcss
REM 2. tailwind.config.js oluştur
npx tailwindcss init
REM 3. Ana CSS dosyasını oluştur
if not exist static\css mkdir static\css
if not exist static\css\tailwind.css (
    echo @tailwind base;> static\css\tailwind.css
    echo @tailwind components;>> static\css\tailwind.css
    echo @tailwind utilities;>> static\css\tailwind.css
)
REM 4. Tailwind'i derle (dev modda izleme)
npx tailwindcss -i ./static/css/tailwind.css -o ./static/css/main.css --watch
