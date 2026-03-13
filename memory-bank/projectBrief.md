## Project Brief
- A local AI agent helper to resolve gaming pc/computer issues by making sure all the settings are optimized for gaming. Including drivers are current, windows settings are accurate to confirm GSYNC with Max FPS limits, removing temp folders and old shader caches etc. It also does local benchmarking to make sure nothing is overheating and provides solutions to solve these issues.
- This approach must be Privacy is 100% guaranteed. No data leaves the device. The only external calls are to verify the current driver version from nvidia/amd/intel websites.



### Phase 1: Architecture & Packaging
To ensure the user downloads just **one combined package** that works entirely offline, we must avoid complex developer setups (no requiring the user to install Python, Docker, or Ollama separately).

*   **The Brain (LLM Engine):** We will use `llama-cpp-python`. This allows you to run quantized GGUF models directly within a Python application. We will bundle a highly capable, small model like `Qwen2.5-Coder-7B-Instruct.Q4_K_M.gguf` (approx. 4.5 GB) which excels at coding, JSON generation, and logic.
*   **The Orchestrator:** Python 3.
*   **The Compiler/Bundler:** Use **Inno Setup** or **NSIS** to create the `.exe` installer. It will unpack the Python environment, the bundled scripts, the GGUF model, and bundled executables (like LibreHardwareMonitor or NvidiaProfileInspector).
*   **Initial Run Verification:** Upon execution, the script hashes all critical files to verify extraction was successful and hasn't been corrupted.

---

### Phase 2: Bootstrapping & System Safety
Before doing *anything*, the application needs to secure the environment.

*   **Privilege Escalation:** The app must immediately request Administrator privileges via Windows UAC.
*   **System Restore Point:** 
    *   *Action:* The tool runs a PowerShell command: `Checkpoint-Computer -Description "Antigravity Pre-Tuning Backup" -RestorePointType "MODIFY_SETTINGS"`
    *   *User Explanation:* The LLM generates a friendly prompt explaining exactly how to restore this snapshot via the Windows Recovery Environment if the PC refuses to boot, ensuring the user feels safe.
*   **The Deep Scan:** 
    *   Run `dxdiag /t dxdiag_output.txt` silently in the background.
    *   Run `nvidiaProfileInspector.exe -exportCurrentProfile nv_profile.nip`.
    *   Run a background instance of **LibreHardwareMonitor** (open-source) to begin logging baseline temperatures and fan speeds.

---

### Phase 3: Implementing the "Choices" UI
The tool presents the extracted system specs to the local LLM, asking it to summarize the hardware, and then presents the user with the two main pathways in a clean terminal or simple PyQt graphical interface.

#### Choice 1: The Configuration Check (The "Esports Check")
This module focuses on ensuring high-end hardware isn't bottlenecked by bad Windows settings.
*   **Monitor Refresh Rate Check:** Python queries Windows Management Instrumentation (WMI) `Win32_VideoController` to check `CurrentRefreshRate`. If the user's monitor supports 240Hz (checked via EDID registry keys) but Windows is set to 60Hz, flag it.
*   **Mouse Polling Rate Check:** *Note: Windows does not natively expose mouse polling rates easily.* The tool can hook into `GetMouseMovePointsEx` to sample USB HID report rates when the user wiggles the mouse for 3 seconds, detecting if it's stuck at 125Hz/500Hz instead of 1000Hz/4000Hz.
*   **Other Checks:** 
    *   Is Windows Game Mode on? (Registry check)
    *   Is Power Management set to Ultimate Performance?
    *   Is XMP/EXPO enabled? (Can be checked via WMI Memory speed vs base spec).
*   **LLM Action:** The LLM reads these flags and outputs a checklist for the user to approve before fixing them via registry/PowerShell.

#### Choice 2: Speed Up My PC
This is the core ReAct loop (Reasoning & Acting) where the tool performs benchmarks, debloats, and verifies.

**Step 2.1: Benchmarking Orchestration**
*   The tool scans for installed benchmarks (3DMark, Cinebench R23/2024, Unigine). If they aren't installed, it can run a lightweight, custom Python multi-threading matrix math test to establish a baseline CPU score.
*   It executes the benchmarks via command-line flags (e.g., triggering Cinebench silently and reading the output log).

**Step 2.2: Aggressive Debloating & Fixes**
*   The LLM compares the benchmark score to the hardware baseline. 
*   It proposes a cleanup list (Human-in-the-Loop approval required):
    *   Clearing `%TEMP%`, `C:\Windows\Temp`, and `C:\Windows\SoftwareDistribution\Download`.
    *   Using the `nv_profile.nip` file to disable G-Sync for specific games, force "Prefer Maximum Performance", and disable Threaded Optimization if applicable.
    *   Disabling known background resource hogs (telemetry services).

**Step 2.3: Thermal Verification & Guidance**
*   While the benchmark ran, LibreHardwareMonitor recorded the `Max_Temperature` of the CPU and GPU.
*   If `CPU_Temp < 80°C`: Output a success message.
*   If `CPU_Temp > 85°C` (or thermal throttling flag is triggered in WMI): The LLM triggers the "Guidance" module.
    *   *Action:* The tool outputs a detailed diagnostic: "Your hardware is thermally throttling. Performance was capped."
    *   *Advice:* "CLEAN YOUR PC U SLOB. Seriously, buy some compressed air. Also, check if your AIO pump is dead or if you need to repaste your CPU."

---

### Phase 4: Development Roadmap & Next Steps

If you want to start building this tomorrow, here is the order of operations to tackle:

1.  **Week 1 (Proof of Concept):** Create a standard Python script that successfully reads monitor refresh rates, checks for `%TEMP%` file sizes, and triggers a system restore point via PowerShell.
2.  **Week 2 (LLM Integration):** Download a local GGUF model (like Qwen2.5-Coder) and write the Python wrapper using `llama-cpp-python`. Feed it a fake `dxdiag` file and ensure it can correctly identify the GPU and propose a JSON list of actions.
3.  **Week 3 (Hardware Hooks):** Integrate LibreHardwareMonitor to read temperatures, and build the command-line orchestrator to trigger Cinebench/3DMark and read their result files.
4.  **Week 4 (Packaging):** Compile the entire Python project using PyInstaller, bundle the GGUF model and executables, and create the final Inno Setup installer.

Which of these pieces would you like to build first? We can start by writing the Python code to perform the **System Restore Backup** and the **Monitor Refresh Rate / Mouse Polling rate checks** right now if you are ready!