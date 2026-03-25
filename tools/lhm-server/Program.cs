// lhm-server — minimal LibreHardwareMonitor sensor HTTP server
// Serves /data.json on localhost:8085 replicating the LHM built-in web server
// format so the lil_bro Python thermal pipeline can consume it without changes.
//
// License: this file is MIT.  LibreHardwareMonitorLib (dependency) is MPL-2.0.
// See LICENSE-LHM.txt for attribution.

using System.Net;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using LibreHardwareMonitor.Hardware;

const int Port = 8085;

// ── Sensor tree snapshot type ─────────────────────────────────────────────────
// Mirrors the JSON structure the LHM HttpServer emits so _parse_temps_from_lhm()
// in thermal_monitor.py can walk it without modification.

sealed record SensorNode(
    [property: JsonPropertyName("Text")]    string Text,
    [property: JsonPropertyName("Value")]   string Value,
    [property: JsonPropertyName("RawValue")] double RawValue,
    [property: JsonPropertyName("Children")] List<SensorNode> Children
);

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

// ── Computer setup ────────────────────────────────────────────────────────────

using var computer = new Computer
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

// Also exit cleanly if lil_bro (parent) terminates: detect closed stdin.
_ = Task.Run(async () =>
{
    try { await Console.In.ReadToEndAsync(cts.Token); }
    catch { /* ignored */ }
    finally { cts.Cancel(); }
}, cts.Token);

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
