#!/bin/bash

# ═══════════════════════════════════════════════════════════════
# 🌙 Night Leech Bot - Setup Script
# ═══════════════════════════════════════════════════════════════

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     🌙 Night Leech Bot - Installation Script        ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════╝${NC}"
echo ""

# ═══════════════════════════════════════════════════════════════
# CHECK PREREQUISITES
# ═══════════════════════════════════════════════════════════════

echo -e "${YELLOW}📋 Checking prerequisites...${NC}"

check_command() {
    if command -v $1 &> /dev/null; then
        echo -e "${GREEN}✅ $1${NC}"
        return 0
    else
        echo -e "${RED}❌ $1${NC}"
        return 1
    fi
}

check_command "git"
check_command "python3"

echo ""
echo -e "${YELLOW}🐳 Checking Docker...${NC}"
if command -v docker &> /dev/null; then
    echo -e "${GREEN}✅ Docker found${NC}"
    DOCKER_INSTALLED=true
else
    echo -e "${YELLOW}⚠️ Docker not found (optional)${NC}"
    DOCKER_INSTALLED=false
fi

# ═══════════════════════════════════════════════════════════════
# UPDATE SYSTEM
# ═══════════════════════════════════════════════════════════════

echo ""
echo -e "${YELLOW}🔄 Updating system packages...${NC}"
if [ "$EUID" -eq 0 ]; then
    apt update && apt upgrade -y
else
    sudo apt update && sudo apt upgrade -y
fi

# ═══════════════════════════════════════════════════════════════
# INSTALL DEPENDENCIES
# ═══════════════════════════════════════════════════════════════

echo ""
echo -e "${YELLOW}📦 Installing Python dependencies...${NC}"

if [ "$EUID" -eq 0 ]; then
    apt install -y python3 python3-pip python3-venv git curl wget
else
    sudo apt install -y python3 python3-pip python3-venv git curl wget
fi

# ═══════════════════════════════════════════════════════════════
# CLONE OR UPDATE PROJECT
# ═══════════════════════════════════════════════════════════════

echo ""
echo -e "${YELLOW}📁 Setting up project directory...${NC}"

PROJECT_DIR="/opt/night-leech"

if [ -d "$PROJECT_DIR" ]; then
    echo -e "${YELLOW}📥 Updating existing installation...${NC}"
    cd "$PROJECT_DIR"
    git pull
else
    echo -e "${YELLOW}📥 Cloning project...${NC}"
    sudo mkdir -p "$PROJECT_DIR"
    sudo chown $(whoami):$(whoami) "$PROJECT_DIR"
    git clone https://github.com/nightclaw77/night-leech.git "$PROJECT_DIR"
    cd "$PROJECT_DIR"
fi

# ═══════════════════════════════════════════════════════════════
# CREATE VIRTUAL ENVIRONMENT
# ═══════════════════════════════════════════════════════════════

echo ""
echo -e "${YELLOW}🐍 Setting up Python virtual environment...${NC}"

python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt 2>/dev/null || echo -e "${YELLOW}⚠️ No requirements.txt found, skipping${NC}"
deactivate

# ═══════════════════════════════════════════════════════════════
# CREATE DIRECTORIES
# ═══════════════════════════════════════════════════════════════

echo ""
echo -e "${YELLOW}📂 Creating directories...${NC}"

mkdir -p downloads
mkdir -p logs
mkdir -p data

# ═══════════════════════════════════════════════════════════════
# CREATE CONFIG FILE
# ═══════════════════════════════════════════════════════════════

echo ""
echo -e "${YELLOW}⚙️ Creating config file...${NC}"

if [ ! -f "config/config.env" ]; then
    cp config/config.env.example config/config.env
    echo -e "${YELLOW}⚠️ Please edit config/config.env with your API keys!${NC}"
else
    echo -e "${YELLOW}⚠️ config/config.env already exists, skipping${NC}"
fi

# ═══════════════════════════════════════════════════════════════
# DOCKER SETUP (OPTIONAL)
# ═══════════════════════════════════════════════════════════════

if [ "$DOCKER_INSTALLED" = false ]; then
    echo ""
    echo -e "${YELLOW}🐳 Installing Docker...${NC}"
    
    if [ "$EUID" -eq 0 ];    
        # Install Docker
        apt install -y apt-transport-https ca-certificates curl software-properties-common
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt key add -
        add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
        apt update
        apt install -y docker-ce docker-ce-cli containerd.io
        
        # Enable Docker
        systemctl start docker
        systemctl enable docker
        
        # Add user to docker group
        usermod -aG docker $(whoami)
        
        echo -e "${GREEN}✅ Docker installed successfully!${NC}"
        echo -e "${YELLOW}⚠️ Please log out and log back in for Docker permissions to take effect${NC}"
    else
        sudo bash -c 'apt install -y apt-transport-https ca-certificates curl software-properties-common && curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt key add - && add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" && sudo apt update && sudo apt install -y docker-ce docker-ce-cli containerd.io && sudo systemctl start docker && sudo systemctl enable docker && sudo usermod -aG docker $(whoami)'
        echo -e "${GREEN}✅ Docker installed successfully!${NC}"
    fi
fi

# ═══════════════════════════════════════════════════════════════
# CREATE SYSTEMD SERVICE
# ═══════════════════════════════════════════════════════════════

echo ""
echo -e "${YELLOW}🔧 Creating systemd service...${NC}"

SERVICE_FILE="/etc/systemd/system/night-leech.service"

if [ ! -f "$SERVICE_FILE" ]; then
    sudo tee $SERVICE_FILE > /dev/null <<EOF
[Unit]
Description=Night Leech Telegram Bot
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/start.sh
Restart=always
RestartSec=10
Environment=PYTHONPATH=$PROJECT_DIR

[Install]
WantedBy=multi-user.target
EOF
    
    sudo systemctl daemon-reload
    echo -e "${GREEN}✅ Service file created${NC}"
else
    echo -e "${YELLOW}⚠️ Service file already exists, skipping${NC}"
fi

# ═══════════════════════════════════════════════════════════════
# FINAL MESSAGE
# ═══════════════════════════════════════════════════════════════

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     ✅ Installation Completed!                      ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}📋 Next Steps:${NC}"
echo ""
echo -e "1. ${BLUE}Edit config file:${NC}"
echo -e "   nano $PROJECT_DIR/config/config.env"
echo ""
echo -e "2. ${BLUE}Add your API keys (see config/api-keys-checklist.md)${NC}"
echo ""
echo -e "3. ${BLUE}Start the bot:${NC}"
echo -e "   cd $PROJECT_DIR && ./start.sh"
echo ""
echo -e "4. ${BLUE}Or with systemd:${NC}"
echo -e "   sudo systemctl enable night-leech"
echo -e "   sudo systemctl start night-leech"
echo ""
echo -e "${YELLOW}📁 Project directory: $PROJECT_DIR${NC}"
echo -e "${YELLOW}📖 Documentation: $PROJECT_DIR/docs/${NC}"
echo ""
