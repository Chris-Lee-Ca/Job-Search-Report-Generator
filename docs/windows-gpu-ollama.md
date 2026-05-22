# Running Ollama on a Windows GPU (remote LLM)

This guide sets up Ollama on a Windows machine with a dedicated GPU (tested on RTX 4070) and connects the Mac pipeline to it over a local WiFi network.

**Why bother?** An RTX 4070 runs `qwen2.5:7b` at ~2–3 seconds/job vs 30–90 seconds on an M1 Mac CPU/Metal. For 200 jobs that's ~10 minutes vs 1–5 hours.

---

## 1. Install Ollama on Windows

**Option A — winget (recommended):**
```powershell
winget install Ollama.Ollama
```

**Option B — direct download:**  
Go to [ollama.com](https://ollama.com) and download the Windows installer. Run it — Ollama installs as a background service and auto-detects your NVIDIA GPU via CUDA.

Verify CUDA is being used after install:
```powershell
ollama ps   # after pulling a model; GPU column should show your card
```

---

## 2. Allow Ollama to accept network connections

By default Ollama only listens on `localhost`. To accept connections from your Mac you need to set the `OLLAMA_HOST` environment variable to `0.0.0.0` at the system level and then restart Ollama.

### Step 2a — Open PowerShell as Administrator

This is required because writing a Machine-level environment variable needs elevated privileges.

1. Press **Windows key**, type `powershell`
2. Right-click **Windows PowerShell** in the results
3. Click **"Run as administrator"**
4. Click **Yes** on the UAC prompt

You should see a blue window with `PS C:\Windows\system32>` — the `system32` path confirms you have admin rights.

### Step 2b — Set the environment variable

Paste this exactly into the PowerShell window and press Enter:

```powershell
[System.Environment]::SetEnvironmentVariable("OLLAMA_HOST", "0.0.0.0", "Machine")
```

No output means it succeeded. Verify it was written:

```powershell
[System.Environment]::GetEnvironmentVariable("OLLAMA_HOST", "Machine")
# Should print: 0.0.0.0
```

> **What "Machine" means:** this writes to `HKEY_LOCAL_MACHINE` in the registry, so the variable applies to all users and all processes (including system services) after they next start. A "User" scope variable would not be read by the Ollama service.

### Step 2c — Restart Ollama so it picks up the new variable

The Ollama process that is currently running was started *before* you set the variable, so it still has the old value. You need to restart it.

**Try the service command first (works if Ollama registered as a Windows service):**

```powershell
Restart-Service ollama
```

If you get `Cannot find any service with service name 'ollama'`, use the manual method below instead.

**Manual restart (always works):**

1. Find the Ollama icon in the system tray (bottom-right corner, near the clock — you may need to click the `^` arrow to see hidden icons)
2. Right-click the icon → **Quit Ollama**
3. Open the **Start menu**, search for **Ollama**, and click it to relaunch

### Step 2d — Verify Ollama is listening on all interfaces

Back in PowerShell (admin not required for this):

```powershell
netstat -an | findstr 11434
```

You should see a line like:
```
TCP    0.0.0.0:11434    0.0.0.0:0    LISTENING
```

The `0.0.0.0:11434` confirms Ollama is now listening on all network interfaces, not just `127.0.0.1:11434`. If you still see `127.0.0.1:11434`, the service didn't pick up the env var — repeat step 2c.

---

## 3. Open Windows Firewall — Mac's IP only

> **Why restrict to your Mac's IP?** Ollama has no built-in authentication. Opening port 11434 to *all* devices on your network means anyone on the same WiFi (or a guest device) can send unlimited requests to your GPU. Scoping to your Mac's IP prevents this.

**First, find your Mac's local IP:**
```bash
# On Mac — run in Terminal
ipconfig getifaddr en0    # WiFi
# or
ifconfig | grep "inet " | grep -v 127.0.0.1
# Example output: 192.168.1.42
```

**Then on Windows — open PowerShell as Administrator:**
```powershell
# Replace 192.168.1.42 with your Mac's actual IP
netsh advfirewall firewall add rule `
  name="Ollama - Mac only" `
  dir=in `
  action=allow `
  protocol=TCP `
  localport=11434 `
  remoteip=192.168.1.42 `
  profile=private
```

This allows port 11434 only from your Mac, only on Private networks (not Public/Domain).

**To remove the rule later:**
```powershell
netsh advfirewall firewall delete rule name="Ollama - Mac only"
```

---

## 4. Pull the model on Windows

Open PowerShell and pull whichever model you want to run:

```powershell
ollama pull qwen2.5:7b    # recommended — fits in 4070's 12GB VRAM
```

| Model | VRAM needed | Est. speed on 4070 | Quality |
|-------|------------|-------------------|---------|
| `qwen2.5:3b` | ~2 GB | ~0.8–1.5 s/job | Lower — misses some skill matches |
| `qwen2.5:7b` | ~4.5 GB | ~2–3 s/job | Good — recommended |
| `qwen2.5:14b` | ~8.5 GB | ~3–5 s/job | Better — fits in 12 GB VRAM |

The 7b model hits the best quality/speed balance for this job scoring task.

---

## 5. Find your Windows machine's local IP

In PowerShell:
```powershell
ipconfig
```

Look for the **IPv4 Address** under your WiFi adapter (e.g. `192.168.1.100`). Note it down — you'll need it in the next step.

---

## 6. Test the connection from your Mac

```bash
# Replace 192.168.1.100 with your Windows IP
curl http://192.168.1.100:11434/api/version
```

Expected response (something like):
```json
{"version":"0.6.x"}
```

If you get a connection refused or timeout, double-check:
- Ollama is running on Windows (check system tray icon)
- `OLLAMA_HOST=0.0.0.0` is set and the service was restarted
- The firewall rule uses your correct Mac IP

---

## 7. Update config.yaml on your Mac

Edit `config/config.yaml` — change the `base_url` to point to your Windows machine:

```yaml
llm:
  provider: ollama
  model: qwen2.5:7b          # or whichever model you pulled on Windows
  base_url: http://192.168.1.100:11434/v1   # replace with your Windows IP
  num_threads: 6             # ignored when running remotely, but harmless
```

No other code changes needed — the pipeline uses this URL for all LLM calls.

---

## 8. Verify end-to-end

Run the benchmark file (2 jobs) and confirm it uses the remote Windows GPU:

```bash
time python main.py score output/raw/benchmark_2jobs.json
```

With `qwen2.5:7b` on the 4070 you should see each job complete in roughly 2–4 seconds (vs 30–90 seconds on the Mac).

---

## Keeping it running

Ollama on Windows runs as a background service and starts automatically on boot. As long as the Windows machine is on and connected to the same WiFi, the Mac pipeline will use it.

If the Windows IP changes (DHCP lease renewal), update `base_url` in `config/config.yaml`. To avoid this, assign a static IP to the Windows machine in your router's DHCP settings.
