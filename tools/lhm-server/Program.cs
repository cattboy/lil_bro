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
// PawnIO.sys is embedded in this exe at build time.  On first run (admin
// required), it is extracted to System32\drivers\ and registered as an
// auto-start kernel service.  Subsequent runs reuse the already-installed
// service — no admin needed after the first launch.

static bool EnsurePawnIoInstalled()
{
    // Check if PawnIO service already exists (sc query returns 0 if present)
    using var check = Process.Start(new ProcessStartInfo("sc", "query PawnIO")
    {
        RedirectStandardOutput = true,
        RedirectStandardError  = true,
        UseShellExecute        = false,
        CreateNoWindow         = true,
    });
    check!.WaitForExit();
    if (check.ExitCode == 0)
        return true;  // already installed — nothing to do

    // Locate embedded PawnIO.sys resource
    var resource = Assembly.GetExecutingAssembly().GetManifestResourceStream("PawnIO.sys");
    if (resource is null)
    {
        Console.Error.WriteLine("[lhm-server] PawnIO.sys not embedded in this build — " +
                                "temperatures may be unavailable.");
        return false;
    }

    // Extract to System32\drivers\
    var sysRoot    = Environment.GetEnvironmentVariable("SystemRoot") ?? @"C:\Windows";
    var driverPath = Path.Combine(sysRoot, "System32", "drivers", "PawnIO.sys");
    try
    {
        using var fs = File.Create(driverPath);
        resource.CopyTo(fs);
    }
    catch (Exception ex)
    {
        Console.Error.WriteLine($"[lhm-server] Failed to write PawnIO.sys: {ex.Message} " +
                                "(run as administrator on first launch)");
        return false;
    }

    // Register and start the kernel service
    if (!RunSc($"create PawnIO binPath= \"{driverPath}\" type= kernel start= auto " +
               "error= normal DisplayName= PawnIO"))
        return false;
    if (!RunSc("start PawnIO"))
        return false;

    // Write Uninstall registry key so PawnIo.IsInstalled returns true
    try
    {
        using var key = Registry.LocalMachine.CreateSubKey(
            @"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\PawnIO");
        key.SetValue("DisplayVersion", "2.2.0");
        key.SetValue("DisplayName", "PawnIO");
    }
    catch { /* non-fatal — driver is running regardless */ }

    Console.WriteLine("[lhm-server] PawnIO driver installed successfully.");
    return true;
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
    return p.ExitCode is 0 or 1056;  // 1056 = service already running
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

        _ = Task.Run(() => HandleRequest(ctx, computer), cts.Token);
    }
}, cts.Token);

await cts.Token.WhenCancelled();

listener.Stop();
computer.Close();

static void HandleRequest(HttpListenerContext ctx, IComputer computer)
{
    var req  = ctx.Request;
    var resp = ctx.Response;

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
