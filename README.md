# How to Recover a Cryptographic Secret From the Cloud

**Status:** ✅ Accepted at **ACM CCS 2025** (artifact available)

**Paper:** “How to Recover a Cryptographic Secret From the Cloud” — also on the [Cryptology ePrint Archive (2023/1308)](https://eprint.iacr.org/2023/1308)

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

  * [Path A: AWS Nitro Enclaves (Real TEE)](#path-a-aws-nitro-enclaves-real-tee)
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

* **Path A (recommended for real TEE results):** Run on **AWS Nitro Enclaves**.
* **Path B (fastest to try locally):** Run the **emulated** setup with Docker.

### Path A: AWS Nitro Enclaves (Real TEE)

**Launch parent instance (choose CLI *or* Console).**

**CLI (example uses `us-east-1`; use the AMI for your region):**

```bash
aws ec2 run-instances --image-id ami-00ca32bbc84273381 --count 1 --instance-type m5.xlarge --key-name your_key_name --security-groups your_security_group_name --enclave-options 'Enabled=true'
```

> Heads-up: Replace `your_key_name` and `your_security_group_name`. Make sure your AMI is valid for your chosen region.

**Console (point-and-click checklist):**

1. EC2 → **Launch instance**
2. AMI: **Amazon Linux 2023 kernel-6.1 (64-bit x86)**
3. Instance type: **m5.xlarge**
4. Key pair: create or select one
5. Security group: default is fine unless you know you need custom rules
6. Storage: bump from **8 GB** to **≥ 30 GB**
7. Advanced details → **Nitro Enclaves: Enable**
8. **Launch**

**Connect to the instance:**

```bash
ssh -i path/to/skrec.pem ec2-user@<public-ip>
```

**Update and install git:**

```bash
sudo yum update -y
```

```bash
sudo yum install git -y
```

**Clone the repo:**

```bash
git clone <repository-url>
```

**Enter the repo:**

```bash
cd <repository-root>
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

```bash
sudo chmod +x tee.sh
```

```bash
./tee.sh run
```

```bash
./tee.sh terminate
```

```bash
./tee.sh console
```

**Verify enclave is up:**

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

**Start the core services.**

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

**Batch runs** (repeat N times; results still append):

```bash
python -m experiments.store -n 10
```

> You can do the same for `retrieve`, `remove`, and `recover` with `-n` or `--num_runs`.

---

## Summarize Results

Once you’ve collected CSVs in `results/`, compute summary stats (min, max, mean, median, stdev):

**General form:**

```bash
python -m experiments.get_stats <input> <output>
```

**Example:**

```bash
python -m experiments.get_stats results/store.csv results/store-summary.csv
```

---

## What this artifact is / isn’t

* **Is:** A research prototype implementation to test the feasibility of our approach to secret-recovery mechanism using TEEs.
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
  Try adding your user to the `docker` group or prefix with `sudo` depending on your OS.
* **Enclave won’t start / limited memory:**
  Double-check `/etc/nitro_enclaves/allocator.yaml` has `memory_mib: 4096` and that you restarted the allocator.
* **AMI or region mix-ups:**
  Make sure your **AMI ID matches your region**. The example uses `us-east-1`.
* **Helper script isn’t executable:**
  Run:

  ```bash
  sudo chmod +x tee.sh
  ```
* **Results files missing:**
  Ensure the `results/` directory exists (it should); commands append to `results/<experiment>.csv`.

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

Happy reproducing!
