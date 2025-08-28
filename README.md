# How to Recover a Cryptographic Secret From the Cloud

**Status:** ✅ Accepted at **ACM CCS 2025** (artifact available)

**Paper:** *How to Recover a Cryptographic Secret From the Cloud* — also on the [Cryptology ePrint Archive (2023/1308)](https://eprint.iacr.org/2023/1308)

-----

## TL;DR (what you’ll do & what you’ll see)

  * Run our implementation either on **AWS Nitro Enclaves** (real TEE) or in a **local emulated** setup (Docker).
  * Execute **store / retrieve / remove / recover** experiments.
  * Collect **timings** into CSVs and generate **summary stats** (min / max / mean / median / stdev).

**If you’re in a hurry:**
Jump to **[Quick Start](#quick-start)** → choose **[AWS Nitro](#path-a-aws-nitro-enclaves-real-tee)** or **[Emulated](#path-b-emulated-environment-docker)** → then **[Run Experiments](#run-experiments)** → **[Summarize Results](#summarize-results)**.

-----

## Table of Contents

  * [Quick Start](#quick-start)
      * [Path A: AWS Nitro Enclaves (Real TEE)](#path-a-aws-nitro-enclaves-real-tee)
      * [Path B: Emulated Environment (Docker)](#path-b-emulated-environment-docker)
  * [Run Experiments](#run-experiments)
  * [Summarize Results](#summarize-results)
  * [What this artifact is / isn’t](#what-this-artifact-is--isnt)
  * [Reproducibility & Environment Notes](#reproducibility--environment-notes)
  * [Troubleshooting](#troubleshooting)
  * [How to Cite](#how-to-cite)
  * [License](#license)

-----

## Quick Start

Pick one of the following paths:

  * **Path A (Recommended):** Run on a real TEE with **AWS Nitro Enclaves**.
  * **Path B (Local Emulation):** Run the emulated setup locally with **Docker**.

If you prefer video guides, we have screen recordings for [Path A - Setup with AWS Nitro](https://youtu.be/fgRPIKa5J48) and [Path B - Docker Emulation](https://youtu.be/rcPudxGSbP8).

-----

### Path A: AWS Nitro Enclaves (Real TEE)

**1. Launch Parent Instance**

You can use the AWS CLI or the AWS Web Management Console.

**Option 1: AWS CLI** (example uses `us-east-1`)

```bash
aws ec2 run-instances \
  --image-id ami-00ca32bbc84273381 \
  --count 1 \
  --instance-type m5.xlarge \
  --key-name your_key_name \
  --security-groups your_security_group_name \
  --enclave-options 'Enabled=true'
```

> **Note:** Replace `your_key_name` and `your_security_group_name`. Ensure the `image-id` (AMI) matches your chosen AWS region.

**Option 2: AWS Management Console**

1.  Go to the **EC2 Dashboard** and click **Launch instance**.
2.  **Name:** Enter any label for your instance.
3.  **Application and OS Images (AMI):** Choose **Amazon Linux → Amazon Linux 2023 kernel-6.1 AMI (64-bit x86)**.
4.  **Instance type:** Select **m5.xlarge**.
5.  **Key pair (login):**
      * If you have a key pair, select it.
      * Otherwise, click **Create new key pair**, name it (e.g., `skrec`), choose **ED25519**, and click **Create key pair**. Your browser will download the private key (e.g., `skrec.pem`). Keep it safe.
6.  **Network settings:**
      * Select an existing security group or choose **Create security group**. The defaults are usually sufficient.
7.  **Configure storage:**
      * Change the default **8 GiB** to **30 GiB** to avoid running out of space.
8.  **Advanced details:**
      * Scroll to **Nitro Enclave** and select **Enable**.
9.  Review the **Summary** panel and click **Launch instance**.

-----

**2. Connect and Set Up the Instance**

**Connect via SSH:**

Find your instance's public IP address in the EC2 console.

```bash
ssh -i path/to/your/skrec.pem ec2-user@<public-ip-address>
```

> If you see a "permissions are too open" error for your `.pem` file, fix it with:
> `chmod 400 path/to/your/skrec.pem`

**Update the instance:**

```bash
sudo yum update -y
```

**Install Git:**

```bash
sudo yum install git -y
```

**Clone the repository:**

```bash
git clone https://github.com/wspr-ncsu/Secret-Recovery.git
```

**Enter the repository directory:**

```bash
cd Secret-Recovery
```

**Run the parent setup script (installs Docker, Docker Compose, nitro-cli):**

Make the script executable first.

```bash
sudo chmod +x aws-parent-setup.sh
```

Then run it.

```bash
./aws-parent-setup.sh
```

**Allocate 4 GiB of memory to the enclave:**

```bash
sudo nano /etc/nitro_enclaves/allocator.yaml
```

> Change `memory_mib: 512` to `memory_mib: 4096`. Save and close the file.

**Restart the allocator service:**

```bash
sudo systemctl restart nitro-enclaves-allocator.service
```

**Create the environment file:**

```bash
cp .env.example .env
```

-----

**3. Manage the Enclave**

Use the helper script `tee.sh` to manage the enclave lifecycle.

**Make the helper script executable:**

```bash
chmod +x tee.sh
```

**Build and run the enclave:**

```bash
./tee.sh run
```

**Verify the enclave is running:**

```bash
nitro-cli describe-enclaves
```

**View the read-only enclave console:**

```bash
./tee.sh console
```

**Destroy the enclave when finished:**

```bash
./tee.sh terminate
```

-----

### Path B: Emulated Environment (Docker)

If you don't have AWS access or prefer a local setup, use the emulated path.

**1. Install Dependencies**

Ensure you have **Docker** and **Docker Compose** installed on your operating system.

**2. Configure the Environment**

**Create the environment file:**

```bash
cp .env.example .env
```

**Edit `.env` to enable emulation:**

Update the following lines to your `.env` file.

```
USE_VSOCK=1
VSOCK_HOST=localhost
VSOCK_PORT=5005
VSOCK_ENV=emulated
```

You are now ready to run the experiments.

-----

## Run Experiments

First, build the core `skrecovery` Docker image.

**Make the build script executable:**

```bash
chmod +x build-skrecovery.sh
```

**Build the image:**

```bash
./build-skrecovery.sh
```

**Start the services:**

The command differs slightly for the real TEE vs. the emulated environment.

**On AWS Nitro (Real TEE):**

```bash
docker compose up -d
```

**In Emulated Mode (Local):**

```bash
docker compose --profile emulated up -d
```

> These commands start the `db`, `ordering-service`, and `experiment` containers.

**Follow logs (optional):**

For the ordering service:

```bash
docker logs -f ordering-service
```

For the emulated enclave (emulated mode only):

```bash
docker logs -f emulated-enclave
```

**Open a shell in the `experiment` container:**

```bash
docker exec -it experiment /bin/bash
```

-----

**Inside the `experiment` container, run the following commands:**

**Register the server and client (run once):**

```bash
python -m experiments.register
```

**Run the `store` experiment:**

```bash
python -m experiments.store
```

**Run the `retrieve` experiment:**

```bash
python -m experiments.retrieve
```

**Run the `remove` experiment:**

```bash
python -m experiments.remove
```

**Run the `recover` experiment:**

```bash
python -m experiments.recover
```

**Run experiments in a batch:**

To run an experiment multiple times, use the `-n` or `--num_runs` flag. To start fresh, you can clear the `experiments/results/` directory before running.

```bash
# Example: Run the 'store' experiment 100 times
python -m experiments.store -n 100
```

-----

## Summarize Results

After collecting data, use the `get_stats.py` script to compute summary statistics (min, max, mean, median, stdev) for each experiment.

**General usage:**

```bash
python -m experiments.get_stats <input_csv_path> <output_csv_path>
```

**Example:**

```bash
python -m experiments.get_stats experiments/results/store.csv experiments/results/store-summary.csv
```

-----

## What this artifact is / isn’t

  * ✅ **Is:** A research prototype to demonstrate the feasibility of our secret recovery mechanism using TEEs.
  * ❌ **Is not:** A production-ready or reference implementation. Please do not deploy this in a production environment.

-----

## Reproducibility & Environment Notes

  * **TEE Path (AWS Nitro Enclaves):**

      * **Parent Instance:** Amazon Linux 2023 (kernel 6.1) on an **m5.xlarge** instance is recommended.
      * **Enclave:** Allocate **≥ 4 GiB** of memory (`memory_mib: 4096`) and **2 vCPUs**.

  * **Emulated Path (Docker):**

      * Any recent version of Docker and Docker Compose on Linux or macOS should work.

  * **Outputs:**

      * Raw, per-run measurements are saved to `experiments/results/*.csv`.
      * Aggregated statistics are generated by `experiments.get_stats`.

  * **Environment Variables:**

      * See `.env.example` for all options. For emulation, ensure `USE_VSOCK=1`, `VSOCK_ENV=emulated`, and `VSOCK_HOST=localhost` are set.

-----

## Troubleshooting

  * **Docker permission denied:** Add your user to the `docker` group (`sudo usmod -aG docker $USER`) and log out/in, or prefix Docker commands with `sudo`.
  * **Enclave fails to start:** Double-check that `/etc/nitro_enclaves/allocator.yaml` has `memory_mib: 4096` and that you restarted the service.
  * **AMI or region mismatch:** Ensure your AMI ID is valid for your selected AWS region.
  * **Helper script isn’t executable:** Run `chmod +x tee.sh` and `./build-skrecovery.sh`.
  * **`TimeoutError: [Errno 110] Connection timed out`:** Ensure the enclave is running (`./tee.sh run`) before starting the experiment services.

If you’re still stuck, please open an issue on our GitHub repository with logs and environment details.

-----

## How to Cite

If this artifact contributes to your research, please cite our paper:

```
@inproceedings{TannerSecretRecovery-CCS2025,
  title     = {How to Recover a Cryptographic Secret From the Cloud},
  author    = {Verber, Tanner and Adei, David and Scafuro, Alessandra and Orsini, Chris},
  booktitle = {Proceedings of the 2025 ACM SIGSAC Conference on Computer and Communications Security (CCS)},
  year      = {2025},
  note      = {Also available as Cryptology ePrint Archive, Report 2023/1308}
}
```

-----

## License

This is research code. Please see the `LICENSE` file in the repository for terms of use.

-----

### Quick Navigation

  * **Run on AWS Nitro?** → [Path A](#path-a-aws-nitro-enclaves-real-tee)
  * **Run with Docker?** → [Path B](#path-b-emulated-environment-docker)
  * **Collect results?** → [Run Experiments](#run-experiments) → [Summarize Results](#summarize-results)

Happy reproducing\! 🎉