# How to Recover a Cryptographic Secret From the Cloud

**Status:** ✅ Accepted at **ACM CCS 2025** (artifact available)

**Paper:** *How to Recover a Cryptographic Secret From the Cloud* — also on the [Cryptology ePrint Archive (2023/1308)](https://eprint.iacr.org/2023/1308)

---

## TL;DR (what you’ll do & what you’ll see)

* Run our implementation either on **AWS Nitro Enclaves** (real TEE) or in a **local emulated** setup (Docker).
* Execute **store / retrieve / remove / recover** experiments.
* Collect **timings** into CSVs and generate **summary stats** (min / max / mean / median / stdev).

**If you’re in a hurry:**
Jump to **[Quick Start](#quick-start)** → choose **[AWS Nitro](#path-a-aws-nitro-enclaves-real-tee)** or **[Emulated](#path-b-emulated-environment-docker)** → then **[Run Experiments](#run-experiments)** → **[Summarize Results](#summarize-results)**.

---

## Table of Contents (jump links)

* [Quick Start](#quick-start)

  * [Path A: AWS Nitro Enclaves](#path-a-aws-nitro-enclaves-real-tee)
  * [Path B: Emulated Environment (Docker)](#path-b-emulated-environment-docker)
* [Run Experiments](#run-experiments)
* [Summarize Results](#summarize-results)
* [What this artifact is / isn’t](#what-this-artifact-is--isnt)
* [Reproducibility & Environment Notes](#reproducibility--environment-notes)
* [Troubleshooting](#troubleshooting)
* [How to Cite](#how-to-cite)
* [License](#license)

---

## Quick Start

Pick one path:

* **Path A (recommended for AWS Nitro):** Run on **AWS Nitro Enclaves**.
* **Path B (Emulated with Docker):** Run the **emulated** setup with Docker.

If you prefer to set up and run our artifacts using YouTube videos, we have provided screen recordings for [Path A - Setup with AWS Nitro](https://youtu.be/fgRPIKa5J48) and [Path B - Docker Emulation](https://youtu.be/rcPudxGSbP8)

---

### Path A: AWS Nitro Enclaves (Real TEE)

**Launch parent instance (choose CLI *or* AWS Web Management Console).**

**CLI (example uses `us-east-1`; use the AMI for your region):**

```bash
aws ec2 run-instances --image-id ami-00ca32bbc84273381 --count 1 --instance-type m5.xlarge --key-name your_key_name --security-groups your_security_group_name --enclave-options 'Enabled=true'
```

> Replace `your_key_name` and `your_security_group_name`. Make sure your AMI ID matches your chosen region.

---

**AWS Management Console:**

1. Go to the **EC2 Dashboard** and click **Launch instance**.
2. Under *Name*, enter any label for your instance.
3. For the AMI, choose **Amazon Linux → Amazon Linux 2023 kernel-6.1 AMI (64-bit x86)**.
4. For the instance type, select **m5.xlarge**.
5. Under *Key pair (login)*:

   * If you already have one, select it.
   * If not, click **Create key pair**, enter a name (e.g., `skrec`), choose **ED25519**, then click **Create key pair**.
   * This will automatically download a private key file (e.g., `skrec.pem`) — keep it safe, you’ll need it to log in.
6. Under *Network settings*:

   * If you already have a security group, select it.
   * Otherwise, select **Create security group**. Defaults are usually fine unless you know you need custom rules.
7. Under *Configure storage*:

   * Change the default **8 GiB** to **30 GiB**. This avoids running out of space mid-experiment.
8. Expand *Advanced details*:

   * Scroll to **Nitro Enclaves**, and select **Enable**.
9. On the right-hand **Summary** panel, click **Launch instance**.

---

**Connect to the instance:**

```bash
ssh -i path/to/skrec.pem ec2-user@<public-ip>
```

Find `<public-ip>` under your instance details in the AWS Console. If you get 
> Permissions 0644 for 'skrec.pem' are too open.
Run the command below to fix the permission of the file:
```bash
sudo chmod 600 skrec.pem
```

---

**Update and install git:**

```bash
sudo yum update -y
```

```bash
sudo yum install git -y
```

**Clone the repo:**

```bash
git clone https://github.com/wspr-ncsu/Secret-Recovery.git
```

**Enter the repo:**

```bash
cd Secret-Recovery
```

**Run parent setup (installs Docker, Docker Compose, nitro-cli):**

```bash
sudo chmod +x aws-parent-setup.sh
```

```bash
./aws-parent-setup.sh
```

> Using a different AMI? See AWS’s Nitro Enclaves install docs if needed.

**Allocate 4 GiB to the enclave:**

```bash
sudo nano /etc/nitro_enclaves/allocator.yaml
```

> Change `memory_mib: 512` → `memory_mib: 4096`, then save and close.

**Restart allocator:**

```bash
sudo systemctl restart nitro-enclaves-allocator.service
```

**Create your environment file:**

```bash
cp .env.example .env
```

**Use the helper to run/stop/inspect the enclave:**
Make script executable:
```bash
sudo chmod +x tee.sh
```

Build and run the enclave:
```bash
./tee.sh run
```

View Read-Only console output of enclave:
```bash
./tee.sh console
```

Destroy the enclave:
```bash
./tee.sh terminate
```

**Verify enclave Status:**

```bash
nitro-cli describe-enclaves
```

---

### Path B: Emulated Environment (Docker)

If you don’t have AWS access (or just want to try it locally), use the **emulated** path.

**Install dependencies:** Docker + Docker Compose (standard installs for your OS).

**Create your environment file:**

```bash
cp .env.example .env
```

**Set emulation options (edit `.env`):**

```
USE_VSOCK=1
VSOCK_HOST=localhost
VSOCK_PORT=5005
VSOCK_ENV=emulated
```

That’s it — you’re ready to spin up the services locally.

---

## Run Experiments

To start the core services, build the `skrecovery` image first.

Make the build script executable:
```bash
sudo chmod +x build-skrecovery.sh
```

Build the docker image:
```bash
./build-skrecovery.sh
```

**On AWS Nitro (real TEE):**

```bash
docker compose up -d
```

**In emulated mode:**

```bash
docker compose --profile emulated up -d
```

> These bring up `db`, `ordering-service`, and `experiment`.

**Follow logs when needed.**

```bash
docker logs -f ordering-service
```

```bash
docker logs -f emulated-enclave
```

> The second command is only for the emulated setup.

**Open a shell in the `experiment` container:**

```bash
docker exec -it experiment /bin/bash
```

**Register server and client (once):**

```bash
python -m experiments.register
```

**Run the experiments (each appends to `results/<name>.csv`):**

```bash
python -m experiments.store
```

```bash
python -m experiments.retrieve
```

```bash
python -m experiments.remove
```

```bash
python -m experiments.recover
```

**Batch runs** (repeat N times). This appends the results to the files. You can delete the contents of `results` folder to start afresh:

```bash
python -m experiments.store -n 10
```

> You can do the same for `retrieve`, `remove`, and `recover` with `-n` or `--num_runs`.

---

## Summarize Results

Once you’ve collected CSVs in `experiments/results/`, compute summary stats (min, max, mean, median, stdev) for each experiment type:

**General form:**

```bash
python -m experiments.get_stats <input> <output>
```

**Example:**

```bash
python -m experiments.get_stats experiments/results/store.csv experiments/results/store-summary.csv
```

---

## What this artifact is / isn’t

* **Is:** A research prototype implementation to test the feasibility of our secret-recovery mechanism using TEEs.
* **Is not:** A production or reference implementation. Please do not deploy this.

---

## Reproducibility & Environment Notes

* **TEE path (AWS Nitro Enclaves):**

  * Parent: Amazon Linux 2023 (kernel 6.1), instance type **m5.xlarge** works well.
  * Enclave: Allocate **≥ 4 GiB** (`memory_mib: 4096`) and **2 vCPUs** (configured by our helper).

* **Emulated path (Docker):**

  * Any recent Docker / Docker Compose on Linux/macOS should be fine.

* **Outputs:**

  * Raw per-run measurements go to `results/*.csv`.
  * Aggregated stats are produced by `experiments.get_stats` into your chosen output path.

* **Environment variables:**

  * See `.env.example`. For emulation, set `USE_VSOCK=1`, `VSOCK_ENV=emulated`, and `VSOCK_HOST=localhost`.

---

## Troubleshooting

* **“Permission denied” with Docker:**
  Add your user to the `docker` group or prefix with `sudo`.

* **Enclave won’t start / limited memory:**
  Double-check `/etc/nitro_enclaves/allocator.yaml` has `memory_mib: 4096` and that you restarted the allocator.

* **AMI or region mix-ups:**
  Make sure your **AMI ID matches your region**. The example uses `us-east-1`.

* **Helper script isn’t executable:**

```bash
sudo chmod +x tee.sh
```

* **Results files missing:**
  Ensure the `results/` directory exists. Commands append to `results/<experiment>.csv`.

* **TimeoutError: [Errno 110] Connection timed out**
  Ensure the enclave is running on the parent instance.


If you’re still stuck, please open a GitHub issue with a short log snippet and your environment details.

---

## How to Cite

If this artifact helped your work, please cite the paper:

```
@inproceedings{TannerSecretRecovery-CCS2025,
  title     = {How to Recover a Cryptographic Secret From the Cloud},
  author    = {Verber, Tanner and Adei, David and Scafuro, Alessandra and Orsini, Chris},
  booktitle = {Proceedings of the 2025 ACM SIGSAC Conference on Computer and Communications Security (CCS)},
  year      = {2025},
  note      = {Also available as Cryptology ePrint Archive, Report 2023/1308}
}
```

---

## License

This is research code. See `LICENSE` in the repository for terms.

---

### Final sign-post (so you can skip back quickly)

* **Just need to run it on AWS Nitro?** → [Path A](#path-a-aws-nitro-enclaves-real-tee)
* **No AWS? Use Docker emulation.** → [Path B](#path-b-emulated-environment-docker)
* **Run and collect results.** → [Run Experiments](#run-experiments) → [Summarize Results](#summarize-results)

Happy reproducing 🎉
