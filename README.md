# How to Recover a Cryptographic Secret From the Cloud
Implementation for How to Recover a Cryptographic Secret From the Cloud Paper. The paper is currently under review but is also public on [Cryptology ePrint Archive](https://eprint.iacr.org/2023/1308).

Abstract
> Clouds have replaced most local backup systems as they offer strong availability and reliability guarantees. Clouds, however, are not (and should not be) used as backup for cryptographic secrets. Cryptographic secrets might control financial assets (e.g., crypto wallets), hence, storing such secrets on the cloud corresponds to sharing ownership of the financial assets with the cloud, and makes the cloud a more attractive target for insider attacks.
> 
> Can we have the best of the two worlds, where a user, Alice,  can conveniently store a copy of her cryptographic secrets on the cloud and she is the only one who can recover them? Can she do so even when she loses her devices and forgets {\em all credentials}, while at the same time retaining full ownership of her secrets?
> 
> In this paper, we provide a cloud-based secret-recovery mechanism using trusted execution environments (TEE) where confidentiality is always guaranteed when Alice has not lost her credentials, even in the presence of a malicious cloud fitted with a TEE. If  Alice loses all her credentials,  she can still recover her secrets (in most circumstances). This is in contrast with all previous work that relies on the assumption that Alice remembers some authentication secret. We prove our system secure in the Universally Composable framework. Further, we implement our protocols and evaluate their performance.

## Setup Parent and Enclave
We have provided 2 options to running the experiments. First with actual AWS Nitro System and Second with Emulated Environment using docker. Feel free to Skip to your required setup instructions for your environment.

### AWS Nitro System Setup
- **Using the Terminal** If you prefer to use `aws-cli` via your terminal, then install the AWS CLI and configure it with your credentials. Then create a parent instance with the following command:
```bash
aws ec2 run-instances \
--image-id ami-00ca32bbc84273381 \
--count 1 \
--instance-type m5.xlarge \
--key-name your_key_name \
--security-groups your_security_group_name \
--enclave-options 'Enabled=true'
```

AWS resources are often region bound so ensure you provide the correct AMI. The AMI used in the command above belongs to the `us-east-1` (N. Virginia) region. Also remember to replace the ```key-name``` and ```security-groups``` with your own values.

- **Using Web Portal** If you prefer to use the AWS Management Console via the Web, then login to AWS console and luanch a new EC2 Instance. Any region will do but we used `us-east-1`. On the EC2 dashboard, 
    1. click `Launch instance` button and enter a name for this instance.
    1. Select `Amazon Linux` AMI and choose `Amazon Linux 2023 kernel-6.1 AMI`, leave the architecture as it is `64-bit (x86)`.
    1. Select `m5.xlarge` as the Instance type.
    1. Select an existing keypair to login with or create a new one if you already do not have it. If you choose to create a new key, it will provide a pop, enter any name you want (e.g skrec), select `ED25519` and click `Create key pair`. This will authomatically download a private key (skrec.pem) which you need to login into the instance.
    1. Under `Network settings`, if you do not already have a security group, select `create security group` and keep the other defaults, unless you know what you're doing then go ahead.
    1. Under `Configure storage`, change the `8` value to something bigger to avoid seeing "annoying" out of space errors. To be safe, we used `30`.
    1. Expand the `Advanced details` section, scroll to `Nitro Enclave` select options and ensure you select `Enable`.
    1. Click `Launch instance` button on the right side of the screen, under the Summary section. 

- **Connect to the parent instance** Run 
    ```bash
    ssh -i path/to/skrec.pem ec2-user@public-ip
    ``` 
    Replace ```path/to/skrec.pem``` with the private key you downloaded and ```public-ip``` with the public IP address of the instance you created. You can find the IP address on the AWS management portal. For more information on how to connect to an instance, see [Connecting to Your Linux Instance Using SSH](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/connect-linux-inst-ssh.html).


- **Instance Setup** Run the following commands to setup the parent instance and install nitro system cli.
    - Update system and install git: 
    ```bash
    sudo yum update -y && sudo yum install git -y
    ```
    - Clone this repository and change directory into the root of this project.
    ```bash 
    git clone repository-url
    ```
    - Install the enclave software on the parent instance using the command 
    ```bash
    sudo chmod +x aws-parent-setup.sh
    ./aws-parent-setup.sh
    ``` 
    This command installs and enables docker, docker compose, and AWS nitro cli. If you are using a different AMI, follow the instructions in the [AWS Nitro Enclaves documentation](https://docs.aws.amazon.com/enclaves/latest/user/nitro-enclave-cli-install.html).

    - Modify the nitro-cli allocator service to allow 4096 MB of memory for the enclave.
        1. Run  ```bash
        sudo nano /etc/nitro_enclaves/allocator.yaml
        ``` 
        and change ```memory_mib: 512``` to ```memory_mib: 4096```. 
        2. Restart the allocator service: 
        ```bash
        sudo systemctl restart nitro-enclaves-allocator.service
        ```
- **Create `.env` File** Create a copy of `.env.example` file as `.env`.

- **Start Enclave Process** We have provided a helper script `tee.sh` to enable you manage the enclave's lifecycle. Run `sudo chmod +x tee.sh` to make the script executable.
    - Build and Run the enclave 
    ```bash
    ./tee.sh run
    ``` 
    This command runs ```nitro-cli``` to build the enclave ```.eif``` file and output enclave measurement information. It assigns 2 vCPUs and 4 GB of memory to the enclave and starts the enclave instance on CID 16. The EnclaveCID is like an IP address for the local socket (vsock) between the parent instance and the enclave. The enclave starts and listens on the vsock port 5005.

    - Stop and terminate the enclave
    ```bash
    ./tee.sh terminate
    ```

    - View the read-only console output of the enclave
    ```bash
    ./tee.sh console
    ```

    - Run the ```nitro-cli describe-enclaves``` command to verify the enclave is running. The output should look like this but not exactly:
    ```json
    {
        "EnclaveID": "i-05f6ed443aEXAMPLE-enc173dfe3eEXAMPLE",
        "ProcessID": 7077,
        "EnclaveCID": 16,
        "NumberOfCPUs": 2,
        "CPUIDs": [
            1,
            3
        ],
        "MemoryMiB": 4096,
        "State": "RUNNING",
        "Flags": "DEBUG_MODE"
    }
    ```

### Emulated Environment Setup
This setup allows you to run the experiments using a docker container to emulate the enclave. This allows you to run end-to-end experiments. 
- **Dependencies**: Make sure you install docker and docker compose on your machine. 
    - **Update `.env`**: If you haven't created `.env` already, create a copy of `.env.example` as `.env`. Then update `VSOCK_HOST` to `localhost` and `VSOCK_ENV` to `emulated`. That section of your `.env` should look something like:
    ```text
    USE_VSOCK=1
    VSOCK_HOST=localhost
    VSOCK_PORT=5005
    VSOCK_ENV=emulated
    ```
    There you go, done with local setup.

## Running Experiments
Follow the instructions below to run the experiments.

- **Start Docker Service**: Run the command below to start docker service (`db`, `ordering-service`, `experiment`). If you're running emulated enclave, add `--profile emulated` to the command:
```bash
docker compose up -d
```
or if emulating the TEE,
```bash
docker compose --profile emulated up -d
```
Both commands starts the ordering service, db and experiment services.

- **View Logs** To view the output of the `ordering-service` run ```docker logs -f ordering-service```. If running emulated environment and want to see the enclave logs, run ```docker logs -f emulated-enclave``` in a separate terminal.

- **Exec and Run Experiments** To execute single runs of the experiments you have to execute bash within the `experiment` service. 
    - Login: ```docker exec -it experiment /bin/bash```. 
    - Register server and client: ```python -m experiments.register```
    - Run Store experiment: ```python -m experiments.store```
    - Run Retrieve experiment: ```python -m experiments.retrieve```
    - Run Remove experiment: ```python -m experiments.remove```
    - Run Recover experiment: ```python -m experiments.recover```

- **Running Multiple end-to-end Experiemnts** Note that the results of the runs will be appended to the respective files in `results/<experiment-type>.csv`. Feel free to delete the contents of `results` but make sure the directory exists. The `store`, `retrieve`, `remove` and `recover` commands above accept `--num_runs` or `-n` option which takes an integer. This runs the given experiment and records the runtimes.


## Summarize Results
Once the experiments are done, you can compute the summary by running the script:
```bash
python -m experiments.get_stats <input> <output>
``` 
Replace `<input>` with the path to the file (e.g `results/store.csv`) and `<output>` with the path to the output summary file (e.g `results/store-summary.csv`).