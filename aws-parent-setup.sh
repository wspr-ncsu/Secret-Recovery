#/bin/bash

sudo dnf update -y
sudo dnf install -y docker

sudo systemctl start docker
sudo systemctl enable docker

sudo usermod -aG docker $USER

sudo curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-$(uname -m) -o /usr/libexec/docker/cli-plugins/docker-compose
sudo chmod +x /usr/libexec/docker/cli-plugins/docker-compose

newgrp docker

sudo dnf install -y aws-nitro-enclaves-cli aws-nitro-enclaves-cli-devel jq

sudo usermod -aG ne $(whoami)
newgrp ne

# Check the installation
nitro-cli --version