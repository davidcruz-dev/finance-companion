#!/bin/bash

# Configuration
RESOURCE_GROUP="finance-companion-rg"
REGISTRY_NAME="financecompanionregistry"
IMAGE_NAME="bitcoin-trading-bot"
CONTAINER_NAME="bitcoin-trading-bot-container"
LOCATION="eastus"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Deploying Bitcoin Trading Bot to Azure Container Instances${NC}"

# Check if Azure CLI is installed and logged in
if ! command -v az &> /dev/null; then
    echo -e "${RED}❌ Azure CLI not found. Please install it first.${NC}"
    exit 1
fi

# Check if logged in to Azure
if ! az account show &> /dev/null; then
    echo -e "${YELLOW}⚠️  Not logged in to Azure. Please run: az login${NC}"
    exit 1
fi

# Create resource group if it doesn't exist
echo -e "${YELLOW}📋 Creating resource group...${NC}"
az group create --name $RESOURCE_GROUP --location $LOCATION

# Create Azure Container Registry if it doesn't exist
echo -e "${YELLOW}🏗️  Creating Azure Container Registry...${NC}"
az acr create --resource-group $RESOURCE_GROUP --name $REGISTRY_NAME --sku Basic --admin-enabled true

# Get ACR login server
ACR_LOGIN_SERVER=$(az acr show --name $REGISTRY_NAME --query loginServer --output tsv)
echo -e "${GREEN}📍 ACR Login Server: $ACR_LOGIN_SERVER${NC}"

# Build and push Docker image
echo -e "${YELLOW}🏗️  Building Docker image...${NC}"
docker build -t $IMAGE_NAME .

echo -e "${YELLOW}🏷️  Tagging image for ACR...${NC}"
docker tag $IMAGE_NAME $ACR_LOGIN_SERVER/$IMAGE_NAME:latest

echo -e "${YELLOW}🔐 Logging in to ACR...${NC}"
az acr login --name $REGISTRY_NAME

echo -e "${YELLOW}⬆️  Pushing image to ACR...${NC}"
docker push $ACR_LOGIN_SERVER/$IMAGE_NAME:latest

# Get ACR credentials
ACR_USERNAME=$(az acr credential show --name $REGISTRY_NAME --query username --output tsv)
ACR_PASSWORD=$(az acr credential show --name $REGISTRY_NAME --query passwords[0].value --output tsv)

echo -e "${YELLOW}🚀 Creating Azure Container Instance...${NC}"

# Create container instance with environment variables
az container create \
    --resource-group $RESOURCE_GROUP \
    --name $CONTAINER_NAME \
    --image $ACR_LOGIN_SERVER/$IMAGE_NAME:latest \
    --registry-login-server $ACR_LOGIN_SERVER \
    --registry-username $ACR_USERNAME \
    --registry-password $ACR_PASSWORD \
    --cpu 1 \
    --memory 1.5 \
    --restart-policy Always \
    --environment-variables \
        TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN" \
        TELEGRAM_USER_ID="$TELEGRAM_USER_ID" \
        FOUNDRY_ENDPOINT="$FOUNDRY_ENDPOINT" \
        FOUNDRY_API_KEY="$FOUNDRY_API_KEY" \
        VISION_ENDPOINT="$VISION_ENDPOINT" \
        VISION_API_KEY="$VISION_API_KEY" \
        CHECK_INTERVAL="$CHECK_INTERVAL"

echo -e "${GREEN}✅ Deployment completed!${NC}"

# Show container status
echo -e "${YELLOW}📊 Container status:${NC}"
az container show --resource-group $RESOURCE_GROUP --name $CONTAINER_NAME --query "{Status:provisioningState,IP:ipAddress.ip}" --output table

echo -e "${GREEN}🎉 Your bot is now running in Azure Container Instances!${NC}"
echo -e "${YELLOW}📝 To view logs: az container logs --resource-group $RESOURCE_GROUP --name $CONTAINER_NAME${NC}"
echo -e "${YELLOW}🔍 To check status: az container show --resource-group $RESOURCE_GROUP --name $CONTAINER_NAME${NC}"