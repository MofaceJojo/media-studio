#!/bin/zsh
cd /Users/mofacejojo/Applications/morpheus-video-studio
export NO_PROXY="127.0.0.1,localhost,::1,10.0.0.29"
export no_proxy="$NO_PROXY"
export PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
./start_web.sh
