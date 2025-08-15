#!/bin/bash
set -e

# --- Configuration ---
# File where the build script saves the running enclave's ID
ENCLAVE_ID_FILE="enclave_id.txt"
# The script that builds and runs a new enclave
BUILD_SCRIPT="./build-and-run-enclave.sh"

# --- Helper Function for Usage ---
usage() {
    echo "Usage: $0 {run|terminate|console|status}"
    echo "  run      : Builds and runs a new enclave."
    echo "  terminate: Terminates the running enclave using the saved ID."
    echo "  console  : Connects to the console of the running enclave."
    echo "  status   : Shows all currently running enclaves."
    exit 1
}

# --- Main Logic ---
# Check if a command was provided
if [ -z "$1" ]; then
    usage
fi

# Process the command
case "$1" in
    run)
        echo "--> Building and running a new enclave..."
        bash "${BUILD_SCRIPT}"
        ;;

    terminate)
        if [ ! -f "${ENCLAVE_ID_FILE}" ]; then
            echo "Error: Enclave ID file not found. Run './enclave.sh run' first." >&2
            exit 1
        fi
        
        EID=$(cat "${ENCLAVE_ID_FILE}")
        echo "--> Terminating enclave ${EID}..."
        sudo nitro-cli terminate-enclave --enclave-id "${EID}"
        
        # Clean up the ID file since the enclave is no longer running
        rm "${ENCLAVE_ID_FILE}"
        echo "Enclave terminated."
        ;;

    console)
        if [ ! -f "${ENCLAVE_ID_FILE}" ]; then
            echo "Error: Enclave ID file not found. Run './enclave.sh run' first." >&2
            exit 1
        fi

        EID=$(cat "${ENCLAVE_ID_FILE}")
        echo "--> Connecting to console for enclave ${EID}..."
        # 'exec' replaces the script process with the console for a clean exit
        exec sudo nitro-cli console --enclave-id "${EID}"
        ;;

    status)
        echo "--> Current enclave status:"
        sudo nitro-cli describe-enclaves
        ;;

    *)
        echo "Error: Unknown command '$1'" >&2
        usage
        ;;
esac