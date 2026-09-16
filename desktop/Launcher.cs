using System;
using System.IO;
using System.Diagnostics;
using System.Reflection;
using System.Windows.Forms;
using System.IO.Compression;
using System.Threading;

class Launcher {
    static void Shortcut(string name, string root, string arguments) {
        Type shellType = Type.GetTypeFromProgID("WScript.Shell");
        if (shellType == null) return;
        object shell = Activator.CreateInstance(shellType);
        string path = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs), name + ".lnk");
        object link = shellType.InvokeMember("CreateShortcut", BindingFlags.InvokeMethod, null, shell, new object[] { path });
        Type type = link.GetType();
        type.InvokeMember("TargetPath", BindingFlags.SetProperty, null, link, new object[] { Path.Combine(root, "SoundShredder.exe") });
        type.InvokeMember("WorkingDirectory", BindingFlags.SetProperty, null, link, new object[] { root });
        type.InvokeMember("Arguments", BindingFlags.SetProperty, null, link, new object[] { arguments });
        type.InvokeMember("Save", BindingFlags.InvokeMethod, null, link, null);
    }

    [STAThread]
    static void Main(string[] args) {
        try {
            string root = AppDomain.CurrentDomain.BaseDirectory;
#if INSTALLER
            root = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", "SoundShredder", "@VERSION@");
            // Versioned installation avoids overwriting files loaded by an older release.
            using (var installLock = new Mutex(false, "Local\\SoundShredder-Installer")) {
            bool acquired;
            try { acquired = installLock.WaitOne(TimeSpan.FromSeconds(30)); }
            catch (AbandonedMutexException) { acquired = true; }
            if (!acquired) throw new Exception("Another SoundShredder installer is running. Wait for it to finish, then reopen this installer.");
            try {
            Directory.CreateDirectory(root);
            string complete = Path.Combine(root, "install-complete.txt");
            if (!File.Exists(complete)) {
            using (var payload = Assembly.GetExecutingAssembly().GetManifestResourceStream("payload.zip"))
            using (var zip = new ZipArchive(payload, ZipArchiveMode.Read)) {
                foreach (var entry in zip.Entries) {
                    string dest = Path.GetFullPath(Path.Combine(root, entry.FullName));
                    if (!dest.StartsWith(Path.GetFullPath(root) + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase)) throw new Exception("Invalid package path.");
                    Directory.CreateDirectory(Path.GetDirectoryName(dest));
                    if (String.IsNullOrEmpty(entry.Name)) continue;
                    using (var source = entry.Open()) using (var target = File.Create(dest)) source.CopyTo(target);
                }
            }
            File.WriteAllText(complete, "@VERSION@");
            }
            Shortcut("SoundShredder", root, "");
            Shortcut("SoundShredder Setup", root, "--setup");
            } finally { installLock.ReleaseMutex(); }
            }
#endif
            string python = Path.Combine(root, "python", "pythonw.exe");
            string script = Path.Combine(root, "desktop", "bootstrap.py");
            if (!File.Exists(python) || !File.Exists(script)) throw new Exception("The app files are incomplete. Run the SoundShredder installer again.");
            string options = Array.IndexOf(args, "--setup") >= 0 ? " --setup" : "";
            if (Array.IndexOf(args, "--no-browser") >= 0) options += " --no-browser";
            Process.Start(new ProcessStartInfo(python, "\"" + script + "\"" + options) { WorkingDirectory = root, UseShellExecute = false, CreateNoWindow = true });
        } catch (Exception e) { MessageBox.Show(e.Message, "SoundShredder setup", MessageBoxButtons.OK, MessageBoxIcon.Error); }
    }
}
