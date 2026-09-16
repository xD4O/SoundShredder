using System;
using System.IO;
using System.Diagnostics;
using System.Reflection;
using System.Windows.Forms;
using System.IO.Compression;

class Launcher {
    [STAThread]
    static void Main() {
        try {
            string root = AppDomain.CurrentDomain.BaseDirectory;
#if INSTALLER
            root = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", "SoundShredder", "1.1.0");
            // Versioned installation avoids overwriting files loaded by an older release.
            Directory.CreateDirectory(root);
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
            string programs = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs), "SoundShredder.lnk");
            Type shellType = Type.GetTypeFromProgID("WScript.Shell");
            if (shellType != null) {
                object shell = Activator.CreateInstance(shellType);
                object link = shellType.InvokeMember("CreateShortcut", BindingFlags.InvokeMethod, null, shell, new object[] { programs });
                Type linkType = link.GetType();
                linkType.InvokeMember("TargetPath", BindingFlags.SetProperty, null, link, new object[] { Path.Combine(root, "SoundShredder.exe") });
                linkType.InvokeMember("WorkingDirectory", BindingFlags.SetProperty, null, link, new object[] { root });
                linkType.InvokeMember("Save", BindingFlags.InvokeMethod, null, link, null);
            }
#endif
            string python = Path.Combine(root, "python", "pythonw.exe");
            string script = Path.Combine(root, "desktop", "bootstrap.py");
            if (!File.Exists(python) || !File.Exists(script)) throw new Exception("The app files are incomplete. Run the SoundShredder installer again.");
            Process.Start(new ProcessStartInfo(python, "\"" + script + "\"") { WorkingDirectory = root, UseShellExecute = false, CreateNoWindow = true });
        } catch (Exception e) { MessageBox.Show(e.Message, "SoundShredder setup", MessageBoxButtons.OK, MessageBoxIcon.Error); }
    }
}
