#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---
ENCLAVE_IMAGE="sk-enclave"
EIF_FILE="sk_enclave.eif"
CONFIG_FILE="enclave-config.json"
ENCLAVE_ID_FILE="enclave_id.txt"

# --- Script ---
echo "--> Building Docker image: ${ENCLAVE_IMAGE}"
docker build --no-cache -t "${ENCLAVE_IMAGE}" -f Dockerfile.enclave .

echo "--> Building Enclave Image File (EIF): ${EIF_FILE}"
sudo nitro-cli build-enclave --docker-uri "${ENCLAVE_IMAGE}" --output-file "${EIF_FILE}"

echo "--> Running enclave and capturing ID..."

# Run the enclave, parse the JSON output for the EnclaveID, and save to a variable
ENCLAVE_ID=$(sudo nitro-cli run-enclave --config "${CONFIG_FILE}" | jq -r .EnclaveID)

# Check if the Enclave ID was successfully captured
if [ -z "${ENCLAVE_ID}" ]; then
    echo "Error: Failed to start enclave or capture Enclave ID." >&2
    exit 1
fi

# Save the captured Enclave ID to a file
echo "${ENCLAVE_ID}" > "${ENCLAVE_ID_FILE}"

echo "Enclave started successfully. ID saved to ${ENCLAVE_ID_FILE}"
echo "Enclave ID: ${ENCLAVE_ID}"

echo "--> Removing temporary Docker image..."
docker image rm "${ENCLAVE_IMAGE}"

echo "Done."