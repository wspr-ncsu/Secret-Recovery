#/bin/bash

sudo dnf update -y
sudo dnf install -y docker

sudo systemctl start docker
sudo systemctl enable docker

sudo usermod -aG docker $USER

newgrp docker

sudo dnf install -y aws-nitro-enclaves-cli aws-nitro-enclaves-cli-devel jq

# Check the installation
nitro-cli --version