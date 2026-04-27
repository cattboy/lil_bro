// lhm-server — minimal LibreHardwareMonitor sensor HTTP server
// Serves /data.json on localhost:8085 replicating the LHM built-in web server
// format so the lil_bro Python thermal pipeline can consume it without changes.
//
// License: this file is MIT.  LibreHardwareMonitorLib (dependency) is MPL-2.0.
// See LICENSE-LHM.txt for attribution.

using System.Diagnostics;
using System.Net;
using System.Reflection;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Threading;
using LibreHardwareMonitor.Hardware;
using Microsoft.Win32;

const int Port = 8085;

// ── Hardware visitor ──────────────────────────────────────────────────────────

static List<SensorNode> BuildTree(IComputer computer)
{
    var hardwareNodes = new List<SensorNode>();

    foreach (var hw in computer.Hardware)
    {
        hw.Update();
        var hwNode = HardwareToNode(hw);
        hardwareNodes.Add(hwNode);
    }

    return hardwareNodes;
}

static SensorNode HardwareToNode(IHardware hw)
{
    // Recursively handle sub-hardware (e.g. CPU cores on some platforms)
    var children = new List<SensorNode>();

    foreach (var sub in hw.SubHardware)
    {
        sub.Update();
        children.Add(HardwareToNode(sub));
    }

    // Group sensors by type; emit only "Temperatures" group
    var tempSensors = hw.Sensors
        .Where(s => s.SensorType == SensorType.Temperature && s.Value.HasValue)
        .ToList();

    if (tempSensors.Count > 0)
    {
        var sensorChildren = tempSensors.Select(s => new SensorNode(
            Text:     s.Name,
            Value:    $"{s.Value!.Value:F1} °C",
            RawValue: Math.Round((double)s.Value!.Value, 2),
            Children: []
        )).ToList();

        children.Add(new SensorNode(
            Text:     "Temperatures",
            Value:    "",
            RawValue: 0,
            Children: sensorChildren
        ));
    }

    return new SensorNode(
        Text:     hw.Name,
        Value:    "",
        RawValue: 0,
        Children: children
    );
}

// ── PawnIO auto-install ───────────────────────────────────────────────────────
// PawnIO.sys from the official namazso/PawnIO.Setup release is WHQL-signed via
// catalog file only (no Authenticode/PE-embedded signature).  Windows DSE
// rejects catalog-only drivers loaded via sc create from System32\drivers.
// The driver MUST go through the Driver Store (pnputil + INF + CAT), and the
// Root\PawnIO device node must exist for LHM to open the ring-0 interface.
//
 // Solution: run pawnio_setup.exe -install -silent, which handles the
// full Driver Store + device node setup correctly. pawnio_setup.exe is
// embedded as a resource and extracted to a temp dir at runtime.

static bool EnsurePawnIoInstalled()
{
    var (serviceExists, serviceRunning) = QueryPawnIoService();
    if (serviceExists && serviceRunning)
        return true;

    if (serviceExists && !serviceRunning)
    {
        // Service registered but stopped — try to start (demand-start after reboot).
        if (RunSc("start PawnIO"))
            return true;
        // Stale entry (wrong arch, previous failed install, etc.) — remove and retry.
        Console.Error.WriteLine("[lhm-server] PawnIO service exists but failed to start " +
                                "-- removing stale entry.");
        RunSc("stop PawnIO");
        RunSc("delete PawnIO");
    }

    // Locate pawnio_setup.exe — embedded resource first, then disk fallback
    // (PyInstaller bundles it next to lhm-server.exe in _MEIPASS/tools/).
    Stream? resource = Assembly.GetExecutingAssembly().GetManifestResourceStream("pawnio_setup.exe");

    string? diskFallback = null;
    if (resource is null)
    {
        var exeDir = Path.GetDirectoryName(Environment.ProcessPath);
        if (exeDir is not null)
        {
            var candidate = Path.Combine(exeDir, "pawnio_setup.exe");
            if (File.Exists(candidate))
                diskFallback = candidate;
        }
    }

    if (resource is null && diskFallback is null)
    {
        Console.Error.WriteLine("[lhm-server] pawnio_setup.exe not embedded and not found on disk -- " +
                                "CPU temperatures will be unavailable.");
        return false;
    }

    // Stage pawnio_setup.exe to a temp dir and run it with NSIS silent flag /S.
    // lil_bro.exe carries uac_admin=True manifest, so lhm-server inherits the
    // elevated token — no UAC prompt is shown.
    var tempDir = Path.Combine(Path.GetTempPath(), $"lil_bro_pawnio_{Environment.ProcessId}");
    try
    {
        Directory.CreateDirectory(tempDir);
        var setupPath = Path.Combine(tempDir, "pawnio_setup.exe");

        using (var fs = File.Create(setupPath))
        {
            if (resource is not null)
            {
                resource.CopyTo(fs);
                resource.Dispose();
            }
            else
            {
                using var src = File.OpenRead(diskFallback!);
                src.CopyTo(fs);
            }
        }

        Console.WriteLine("[lhm-server] Installing PawnIO via Driver Store (pawnio_setup.exe -install -silent) ...");
        using var p = Process.Start(new ProcessStartInfo(setupPath, "-install -silent")
        {
            UseShellExecute  = false,
            CreateNoWindow   = true,
            WorkingDirectory = tempDir,
        });

        if (p is null)
        {
            Console.Error.WriteLine("[lhm-server] Failed to launch pawnio_setup.exe.");
            return false;
        }

        if (!p.WaitForExit(60_000))
        {
            p.Kill();
            Console.Error.WriteLine("[lhm-server] pawnio_setup.exe timed out after 60s.");
            return false;
        }

        if (p.ExitCode != 0)
        {
            Console.Error.WriteLine($"[lhm-server] pawnio_setup.exe exited with code {p.ExitCode}.");
            return false;
        }
    }
    catch (Exception ex)
    {
        Console.Error.WriteLine($"[lhm-server] Failed to run pawnio_setup.exe: {ex.Message}");
        return false;
    }
    finally
    {
        try { Directory.Delete(tempDir, recursive: true); }
        catch { /* non-fatal */ }
    }

    // Poll for the PawnIO service to appear — Driver Store install and sc start
    // happen asynchronously inside pawnio_setup.exe.
    for (int i = 0; i < 20; i++)
    {
        Thread.Sleep(500);
        var (exists, running) = QueryPawnIoService();
        if (exists && running)
        {
            Console.WriteLine("[lhm-server] PawnIO installed and running via Driver Store.");
            return true;
        }
    }

    // pawnio_setup.exe may use StartType=demand — try an explicit sc start.
    if (RunSc("start PawnIO"))
    {
        Console.WriteLine("[lhm-server] PawnIO service started.");
        return true;
    }

    Console.Error.WriteLine("[lhm-server] PawnIO installed but service did not start.");
    return false;
}

static (bool exists, bool running) QueryPawnIoService()
{
    using var p = Process.Start(new ProcessStartInfo("sc", "query PawnIO")
    {
        RedirectStandardOutput = true,
        RedirectStandardError  = true,
        UseShellExecute        = false,
        CreateNoWindow         = true,
    });
    p!.WaitForExit();

    if (p.ExitCode != 0)
        return (false, false);

    // Parse sc query output -- look for "STATE" line containing "RUNNING"
    var output = p.StandardOutput.ReadToEnd();
    var running = output.Contains("RUNNING", StringComparison.OrdinalIgnoreCase);
    return (true, running);
}

static bool RunSc(string args)
{
    using var p = Process.Start(new ProcessStartInfo("sc", args)
    {
        UseShellExecute        = false,
        CreateNoWindow         = true,
        RedirectStandardOutput = true,
        RedirectStandardError  = true,
    });
    p!.WaitForExit();
    if (p.ExitCode is 0 or 1056)  // 1056 = service already running
        return true;
    var stderr = p.StandardError.ReadToEnd().Trim();
    var stdout = p.StandardOutput.ReadToEnd().Trim();
    Console.Error.WriteLine($"[lhm-server] sc {args.Split(' ')[0]} failed (exit {p.ExitCode})" +
                            (stdout.Length > 0 ? $": {stdout}" : "") +
                            (stderr.Length > 0 ? $" | {stderr}" : ""));
    return false;
}

EnsurePawnIoInstalled();

// ── Computer setup ────────────────────────────────────────────────────────────

var computer = new Computer
{
    IsCpuEnabled         = true,
    IsGpuEnabled         = true,
    IsMotherboardEnabled = true,  // includes CPU VRM and some ambient sensors
    IsStorageEnabled     = false,
    IsNetworkEnabled     = false,
    IsMemoryEnabled      = false,
    IsBatteryEnabled     = false,
    IsControllerEnabled  = false,
};

computer.Open();

// ── Background sensor update loop ─────────────────────────────────────────────

using var cts = new CancellationTokenSource();

Console.CancelKeyPress += (_, e) =>
{
    e.Cancel = true;
    cts.Cancel();
};

// Exit cleanly when the parent process (lil_bro) terminates.
// Accepts --parent-pid <pid> so this works whether we were launched as a
// direct child process (stdin pipe) or via ShellExecuteW elevation (no pipe).
var cmdArgs  = Environment.GetCommandLineArgs();
var ppIdx    = Array.IndexOf(cmdArgs, "--parent-pid");
if (ppIdx >= 0 && ppIdx + 1 < cmdArgs.Length &&
    int.TryParse(cmdArgs[ppIdx + 1], out int parentPid))
{
    _ = Task.Run(async () =>
    {
        while (!cts.Token.IsCancellationRequested)
        {
            try { Process.GetProcessById(parentPid); }
            catch (ArgumentException) { cts.Cancel(); break; }  // parent gone
            try { await Task.Delay(2000, cts.Token); }
            catch (OperationCanceledException) { break; }
        }
    });
}

var updateTask = Task.Run(async () =>
{
    while (!cts.Token.IsCancellationRequested)
    {
        foreach (var hw in computer.Hardware)
        {
            hw.Update();
            foreach (var sub in hw.SubHardware)
                sub.Update();
        }
        try { await Task.Delay(1000, cts.Token); }
        catch (OperationCanceledException) { break; }
    }
}, cts.Token);

// ── HTTP listener ─────────────────────────────────────────────────────────────

using var listener = new HttpListener();
listener.Prefixes.Add($"http://localhost:{Port}/");
listener.Start();

Console.WriteLine($"lhm-server listening on http://localhost:{Port}/data.json");

var serveTask = Task.Run(async () =>
{
    while (!cts.Token.IsCancellationRequested)
    {
        HttpListenerContext ctx;
        try
        {
            ctx = await listener.GetContextAsync();
        }
        catch (HttpListenerException) { break; }
        catch (ObjectDisposedException) { break; }

        _ = Task.Run(() => HandleRequest(ctx, computer, cts), cts.Token);
    }
}, cts.Token);

await cts.Token.WhenCancelled();

listener.Stop();
computer.Close();

static void HandleRequest(HttpListenerContext ctx, IComputer computer, CancellationTokenSource cts)
{
    var req  = ctx.Request;
    var resp = ctx.Response;

    // Graceful-shutdown endpoint: lil_bro POSTs/GETs /shutdown so computer.Close()
    // runs (releasing the PawnIO driver handle) before the SCM service is removed.
    // Ack first so the client sees 200 before the listener tears down.
    if (req.Url?.AbsolutePath == "/shutdown")
    {
        try
        {
            var bytes = Encoding.UTF8.GetBytes("shutting down");
            resp.ContentType     = "text/plain";
            resp.ContentLength64 = bytes.Length;
            resp.StatusCode      = 200;
            resp.OutputStream.Write(bytes);
        }
        catch { /* best effort — cancel even if response failed */ }
        finally
        {
            try { resp.Close(); } catch { /* ignore */ }
        }
        cts.Cancel();
        return;
    }

    if (req.Url?.AbsolutePath != "/data.json")
    {
        resp.StatusCode = 404;
        resp.Close();
        return;
    }

    try
    {
        var tree = new SensorNode(
            Text:     "Sensor",
            Value:    "",
            RawValue: 0,
            Children: BuildTree(computer)
        );

        var json = JsonSerializer.Serialize(tree, new JsonSerializerOptions
        {
            WriteIndented = false,
        });

        var bytes = Encoding.UTF8.GetBytes(json);
        resp.ContentType     = "application/json";
        resp.ContentLength64 = bytes.Length;
        resp.OutputStream.Write(bytes);
    }
    catch (Exception ex)
    {
        Console.Error.WriteLine($"Request error: {ex.Message}");
        resp.StatusCode = 500;
    }
    finally
    {
        resp.Close();
    }
}

// ── Sensor tree snapshot type ─────────────────────────────────────────────────
// Mirrors the JSON structure the LHM HttpServer emits so _parse_temps_from_lhm()
// in thermal_monitor.py can walk it without modification.
// NOTE: type declarations must follow all top-level statements in C# 9+ programs.

sealed record SensorNode(
    [property: JsonPropertyName("Text")]    string Text,
    [property: JsonPropertyName("Value")]   string Value,
    [property: JsonPropertyName("RawValue")] double RawValue,
    [property: JsonPropertyName("Children")] List<SensorNode> Children
);

// ── Helper ────────────────────────────────────────────────────────────────────

static class CancellationTokenExtensions
{
    public static Task WhenCancelled(this CancellationToken ct)
    {
        var tcs = new TaskCompletionSource();
        ct.Register(() => tcs.TrySetResult());
        return tcs.Task;
    }
}
