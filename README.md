# How to Recover a Cryptographic Secret From the Cloud

This repository contains the **implementation and experimental artifacts** for the paper:
**“How to Recover a Cryptographic Secret From the Cloud”**, Accepted at ACM CCS 2025 and also available on the [Cryptology ePrint Archive (2023/1308)](https://eprint.iacr.org/2023/1308).

---

## Abstract

> Cloud services have largely replaced local backup systems due to their strong availability and reliability guarantees. However, clouds are not (and should not be) trusted as backups for cryptographic secrets. Such secrets may control financial assets (e.g., crypto wallets), so storing them in the cloud effectively transfers partial ownership to the cloud and increases the risk of insider attacks.
>
> Can we achieve the best of both worlds—convenient cloud storage of cryptographic secrets while ensuring that only the owner, Alice, can recover them? Even in the extreme case where she loses all devices and credentials?
>
> We propose a cloud-based secret recovery mechanism leveraging Trusted Execution Environments (TEEs). Our system guarantees confidentiality against a malicious cloud equipped with a TEE, unless Alice has lost all credentials. In that worst case, Alice can still recover her secrets (in most circumstances). This is the first system to support recovery without assuming the user remembers any authentication secret. We formally prove security in the Universally Composable (UC) framework and implement our protocols, evaluating their performance in practice.

---

## Environment Setup

You can run the experiments in two ways:

1. **On real hardware** using **AWS Nitro Enclaves**.
2. **Locally** with an **emulated enclave environment via Docker**.

Skip directly to the option most relevant to you.

---

### 1. AWS Nitro Enclaves Setup

#### Launch Parent Instance

* **Using AWS CLI**

```bash
aws ec2 run-instances \
--image-id ami-00ca32bbc84273381 \
--count 1 \
--instance-type m5.xlarge \
--key-name your_key_name \
--security-groups your_security_group_name \
--enclave-options 'Enabled=true'
```

⚠️ Ensure the AMI corresponds to your region (`us-east-1` in this example). Replace `key-name` and `security-groups` with your own.

---

* **Using AWS Web Console**

1. Go to **EC2 Dashboard → Launch instance**.
2. Select **Amazon Linux 2023 kernel-6.1 AMI (64-bit x86)**.
3. Choose instance type: `m5.xlarge`.
4. Configure **key pair** (create or reuse).
5. Configure **security group** (use default unless customizing).
6. Increase **storage** from `8 GB` to at least `30 GB`.
7. Expand **Advanced details → Nitro Enclaves** → **Enable**.
8. Click **Launch instance**.

---

#### Connect to the Parent Instance

```bash
ssh -i path/to/skrec.pem ec2-user@<public-ip>
```

Replace `path/to/skrec.pem` with your key and `<public-ip>` with the instance’s public IP.

---

#### Instance Setup

Update system and install git:

```bash
sudo yum update -y
```

```bash
sudo yum install git -y
```

Clone this repository:

```bash
git clone <repository-url>
```

Change into the repository root:

```bash
cd <repository-root>
```

Run setup script (installs docker, docker-compose, nitro-cli):

```bash
sudo chmod +x aws-parent-setup.sh
```

```bash
./aws-parent-setup.sh
```

If using a different AMI, follow [AWS Nitro Enclaves Documentation](https://docs.aws.amazon.com/enclaves/latest/user/nitro-enclave-cli-install.html).

---

#### Configure Enclave Memory

Edit allocator config:

```bash
sudo nano /etc/nitro_enclaves/allocator.yaml
```

Change `memory_mib: 512` → `memory_mib: 4096`.

Restart service:

```bash
sudo systemctl restart nitro-enclaves-allocator.service
```

---

#### Create Environment File

```bash
cp .env.example .env
```

---

#### Start Enclave Lifecycle

Make helper script executable:

```bash
sudo chmod +x tee.sh
```

Build and run enclave:

```bash
./tee.sh run
```

Terminate enclave:

```bash
./tee.sh terminate
```

View console logs:

```bash
./tee.sh console
```

Verify enclave status:

```bash
nitro-cli describe-enclaves
```

---

### 2. Emulated Environment (Docker)

This option runs experiments locally without AWS hardware.

#### Dependencies

Install **Docker** and **Docker Compose**.

#### Configure Environment

```bash
cp .env.example .env
```

Update `.env` file:

```text
USE_VSOCK=1
VSOCK_HOST=localhost
VSOCK_PORT=5005
VSOCK_ENV=emulated
```

Done! You’re ready to run locally.

---

## Running Experiments

#### Start Services

On AWS Nitro:

```bash
docker compose up -d
```

In emulated environment:

```bash
docker compose --profile emulated up -d
```

This launches: `db`, `ordering-service`, and `experiment`.

---

#### Logs

Ordering service logs:

```bash
docker logs -f ordering-service
```

Enclave logs (emulated only):

```bash
docker logs -f emulated-enclave
```

---

#### Execute Experiments

Open a shell inside the experiment container:

```bash
docker exec -it experiment /bin/bash
```

Register server and client:

```bash
python -m experiments.register
```

Run store experiment:

```bash
python -m experiments.store
```

Run retrieve experiment:

```bash
python -m experiments.retrieve
```

Run remove experiment:

```bash
python -m experiments.remove
```

Run recover experiment:

```bash
python -m experiments.recover
```

Results are appended to `results/<experiment>.csv`.

---

#### Multiple Runs

Use the `--num_runs` (or `-n`) flag:

```bash
python -m experiments.store -n 50
```

---

## Summarizing Results

After running experiments, compute summary statistics:

```bash
python -m experiments.get_stats <input> <output>
```

Example:

```bash
python -m experiments.get_stats results/store.csv results/store-summary.csv
```

This outputs min, max, mean, median, and standard deviation.
