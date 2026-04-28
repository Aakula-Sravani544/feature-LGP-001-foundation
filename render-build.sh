#!/usr/bin/env bash
# exit on error
set -o errexit

# Define the storage directory for Chrome
STORAGE_DIR=/opt/render/project/.render

# Create the directory if it doesn't exist
if [ ! -d "$STORAGE_DIR/chrome" ]; then
  echo "...Downloading and Installing Chrome"
  mkdir -p $STORAGE_DIR/chrome
  cd $STORAGE_DIR/chrome
  # Download the latest stable Chrome .deb package
  wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
  # Extract the package without needing root permissions
  dpkg -x google-chrome-stable_current_amd64.deb .
  # Clean up the .deb file
  rm google-chrome-stable_current_amd64.deb
  cd -
else
  echo "...Chrome is already installed in $STORAGE_DIR/chrome"
fi

# Ensure Python dependencies are installed
pip install -r requirements.txt
