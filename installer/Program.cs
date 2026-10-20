using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Drawing;
using System.IO;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Forms;

[assembly: AssemblyTitle("CodeX Pets Installer")]
[assembly: AssemblyProduct("CodeX Pets")]
[assembly: AssemblyDescription("小白和小鸡毛 · Codex 自定义宠物安装器")]
[assembly: AssemblyVersion("1.0.0.0")]
[assembly: AssemblyFileVersion("1.0.0.0")]

namespace CodeXPets
{
    internal static class Program
    {
        [STAThread]
        private static int Main(string[] args)
        {
            string reportPath = null;
            try
            {
                if (args.Length == 2 && args[0] == "--verify-assets")
                {
                    reportPath = args[1];
                    WriteReport(reportPath, Engine.VerifyAssets());
                    return 0;
                }
                if (args.Length == 4 && args[0] == "--install-to" && args[2] == "--report")
                {
                    reportPath = args[3];
                    WriteReport(reportPath, Engine.Install(args[1]));
                    return 0;
                }
                Application.EnableVisualStyles();
                Application.SetCompatibleTextRenderingDefault(false);
                if ((args.Length == 2 || args.Length == 3) && args[0] == "--render-preview")
                {
                    using (InstallerForm form = new InstallerForm())
                    {
                        if (args.Length == 3) form.Font = new Font("Segoe UI", 12F);
                        form.StartPosition = FormStartPosition.Manual;
                        form.Location = new Point(-30000, -30000);
                        form.ShowInTaskbar = false;
                        form.Show();
                        Application.DoEvents();
                        form.PerformAutoScale();
                        form.PerformLayout();
                        using (Bitmap image = new Bitmap(form.Width, form.Height))
                        {
                            form.DrawToBitmap(image, new Rectangle(Point.Empty, image.Size));
                            image.Save(args[1], System.Drawing.Imaging.ImageFormat.Png);
                        }
                        form.Hide();
                    }
                    return 0;
                }
                if (args.Length != 0) throw new ArgumentException("无法识别命令行参数。");
                using (Mutex mutex = new Mutex(false, "Local\\CodeXPetsInstaller"))
                {
                    if (!mutex.WaitOne(0, false))
                    {
                        MessageBox.Show("另一个宠物安装器正在运行。", "CodeX Pets");
                        return 2;
                    }
                    try { Application.Run(new InstallerForm()); }
                    finally { mutex.ReleaseMutex(); }
                }
                return 0;
            }
            catch (Exception error)
            {
                if (reportPath != null)
                    WriteReport(reportPath, new Dictionary<string, object> { { "ok", false }, { "error", error.Message } });
                else if (args.Length == 0)
                    MessageBox.Show("安装器无法启动：" + error.Message, "CodeX Pets", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return 1;
            }
        }

        private static void WriteReport(string path, object value)
        {
            File.WriteAllText(path, new JavaScriptSerializer().Serialize(value), new UTF8Encoding(false));
        }
    }

    internal sealed class InstallResult
    {
        public bool ok { get; set; }
        public string target { get; set; }
        public string backup { get; set; }
        public string spriteSha256 { get; set; }
    }

    internal static class Engine
    {
        internal const string PetId = "maltese-retriever";
        internal const string DisplayName = "小白和小鸡毛";

        internal static byte[] Resource(string name)
        {
            using (Stream stream = Assembly.GetExecutingAssembly().GetManifestResourceStream(name))
            {
                if (stream == null) throw new InvalidDataException("安装资源不完整：" + name);
                using (MemoryStream buffer = new MemoryStream())
                {
                    stream.CopyTo(buffer);
                    return buffer.ToArray();
                }
            }
        }

        internal static string Hash(byte[] bytes)
        {
            using (SHA256 sha = SHA256.Create())
                return BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-", "").ToLowerInvariant();
        }

        internal static Dictionary<string, object> VerifyAssets()
        {
            byte[] sprite = Resource("CodeXPets.Sprite");
            byte[] manifest = Resource("CodeXPets.Manifest");
            byte[] preview = Resource("CodeXPets.Preview");
            if (Hash(sprite) != BuildInfo.SpriteSha256 || Hash(manifest) != BuildInfo.ManifestSha256 || Hash(preview) != BuildInfo.PreviewSha256)
                throw new InvalidDataException("安装资源校验失败，请重新复制完整的安装器。");
            if (sprite.Length > 20 * 1024 * 1024 || sprite.Length < 16)
                throw new InvalidDataException("宠物图集大小不正确。");
            if (Encoding.ASCII.GetString(sprite, 0, 4) != "RIFF" || Encoding.ASCII.GetString(sprite, 8, 4) != "WEBP")
                throw new InvalidDataException("宠物图集格式不正确。");
            Dictionary<string, object> meta = new JavaScriptSerializer().Deserialize<Dictionary<string, object>>(Encoding.UTF8.GetString(manifest));
            if ((string)meta["id"] != PetId || (string)meta["spritesheetPath"] != "spritesheet.webp" || Convert.ToInt32(meta["spriteVersionNumber"]) != 2)
                throw new InvalidDataException("宠物配置不符合当前版本要求。");
            using (MemoryStream stream = new MemoryStream(preview))
            using (Image image = Image.FromStream(stream))
                if (image.Width != 192 || image.Height != 208)
                    throw new InvalidDataException("动效预览尺寸不正确。");
            return new Dictionary<string, object> { { "ok", true }, { "spriteSha256", Hash(sprite) }, { "manifestSha256", Hash(manifest) }, { "previewSha256", Hash(preview) } };
        }

        internal static string DefaultHome()
        {
            string configured = Environment.GetEnvironmentVariable("CODEX_HOME");
            string profile = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
            if (String.IsNullOrWhiteSpace(configured)) return Path.Combine(profile, ".codex");
            configured = Environment.ExpandEnvironmentVariables(configured.Trim());
            if (configured.StartsWith("~/") || configured.StartsWith("~\\")) configured = Path.Combine(profile, configured.Substring(2));
            return Path.GetFullPath(configured);
        }

        private static string Child(string parent, string name)
        {
            string root = Path.GetFullPath(parent).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
            string child = Path.GetFullPath(Path.Combine(root, name));
            if (!String.Equals(Path.GetDirectoryName(child), root, StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException("安装路径校验失败。");
            return child;
        }

        private static void WriteFile(string path, byte[] data)
        {
            using (FileStream file = new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.None))
            {
                file.Write(data, 0, data.Length);
                file.Flush(true);
            }
        }

        internal static InstallResult Install(string inputHome)
        {
            VerifyAssets();
            if (String.IsNullOrWhiteSpace(inputHome) || !Path.IsPathRooted(inputHome))
                throw new ArgumentException("请选择 Codex 配置目录的完整路径。");
            string home = Path.GetFullPath(inputHome);
            string pets = Child(home, "pets");
            string target = Child(pets, PetId);
            string staging = Child(home, ".pet-installer-" + Guid.NewGuid().ToString("N"));
            string backup = null;
            bool committed = false;
            try
            {
                Directory.CreateDirectory(home);
                Directory.CreateDirectory(pets);
                if (File.Exists(target)) throw new IOException("目标位置存在同名文件，请更换 Codex 配置目录或先处理该文件。");
                Directory.CreateDirectory(staging);
                WriteFile(Child(staging, "pet.json"), Resource("CodeXPets.Manifest"));
                WriteFile(Child(staging, "spritesheet.webp"), Resource("CodeXPets.Sprite"));
                if (Hash(File.ReadAllBytes(Child(staging, "spritesheet.webp"))) != BuildInfo.SpriteSha256)
                    throw new IOException("写入校验失败，原有宠物没有被替换。");
                if (Directory.Exists(target))
                {
                    string backups = Child(home, "pet-backups");
                    Directory.CreateDirectory(backups);
                    backup = Child(backups, PetId + "-" + DateTime.Now.ToString("yyyyMMdd-HHmmss") + "-" + Guid.NewGuid().ToString("N").Substring(0, 8));
                    Directory.Move(target, backup);
                }
                Directory.Move(staging, target);
                committed = true;
                return new InstallResult { ok = true, target = target, backup = backup, spriteSha256 = BuildInfo.SpriteSha256 };
            }
            catch
            {
                if (!committed && backup != null && Directory.Exists(backup) && !Directory.Exists(target))
                    Directory.Move(backup, target);
                throw;
            }
            finally
            {
                // Only our uniquely named staging directory is ever removed.
                if (Directory.Exists(staging)) Directory.Delete(staging, true);
            }
        }
    }

    internal sealed class InstallerForm : Form
    {
        private readonly TextBox home;
        private readonly Label status;
        private readonly Button install;
        private readonly Button browse;
        private readonly Button close;
        private readonly Button openFolder;
        private readonly ProgressBar progress;
        private readonly MemoryStream previewStream;
        private readonly Image preview;
        private bool installing;
        private string installedPath;

        internal InstallerForm()
        {
            Engine.VerifyAssets();
            Text = "CodeX Pets 安装器 · 1.0.0";
            Font = new Font("Segoe UI", 9.5F);
            AutoScaleMode = AutoScaleMode.Font;
            AutoScaleDimensions = new SizeF(6F, 13F);
            BackColor = SystemColors.Window;
            ForeColor = SystemColors.WindowText;
            ClientSize = new Size(760, 540);
            MinimumSize = new Size(720, 560);
            StartPosition = FormStartPosition.CenterScreen;
            MaximizeBox = false;

            TableLayoutPanel root = new TableLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(24), ColumnCount = 1, RowCount = 5 };
            foreach (int height in new int[] { 68, 220, 72, 74, 58 }) root.RowStyles.Add(new RowStyle(SizeType.Absolute, height));
            root.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            Controls.Add(root);

            Panel heading = new Panel { Dock = DockStyle.Fill };
            Label title = new Label { Text = Engine.DisplayName, Font = new Font("Segoe UI", 20F, FontStyle.Bold), AutoSize = true, Location = new Point(0, 0) };
            Label subtitle = new Label { Text = "把喜欢的伙伴带到 Codex", AutoSize = true, Location = new Point(2, 39) };
            heading.Controls.Add(title); heading.Controls.Add(subtitle); root.Controls.Add(heading, 0, 0);

            TableLayoutPanel content = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2, RowCount = 1, Margin = Padding.Empty };
            content.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 264)); content.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            Panel previewPanel = new Panel { Dock = DockStyle.Fill, BackColor = Color.FromArgb(255, 249, 242), Margin = new Padding(0, 0, 24, 0) };
            previewStream = new MemoryStream(Engine.Resource("CodeXPets.Preview")); preview = Image.FromStream(previewStream);
            PictureBox picture = new PictureBox { Dock = DockStyle.Fill, Image = preview, SizeMode = PictureBoxSizeMode.Zoom, AccessibleName = "小白和小鸡毛原生待机动效预览" };
            previewPanel.Controls.Add(picture); content.Controls.Add(previewPanel, 0, 0);
            TableLayoutPanel details = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 4, Margin = Padding.Empty };
            foreach (int height in new int[] { 54, 54, 54, 58 }) details.RowStyles.Add(new RowStyle(SizeType.Absolute, height));
            details.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            details.Controls.Add(Body("开心地靠在一起\n小鸡毛摇尾，粉色爱心向上冒出。"), 0, 0);
            details.Controls.Add(Body("Windows 10 / Windows 11\n单文件安装器，无需额外安装 Node 或 Python。"), 0, 1);
            details.Controls.Add(Body("已有同名宠物会先备份。\n安装器不会修改其他宠物或 Codex 设置。"), 0, 2);
            Label timing = Body("此处显示 Codex 原生 6 帧播放效果，\n节奏比聊天中的 28 帧演示更简洁。");
            timing.ForeColor = SystemColors.GrayText; details.Controls.Add(timing, 0, 3);
            content.Controls.Add(details, 1, 0); root.Controls.Add(content, 0, 1);

            TableLayoutPanel directory = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2, RowCount = 2, Margin = new Padding(0, 12, 0, 0) };
            directory.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100)); directory.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 100));
            directory.RowStyles.Add(new RowStyle(SizeType.Absolute, 22)); directory.RowStyles.Add(new RowStyle(SizeType.Absolute, 34));
            Label directoryLabel = new Label { Text = "Codex 配置目录（通常为用户目录下的 .codex）", Dock = DockStyle.Fill, AutoSize = false };
            directory.Controls.Add(directoryLabel, 0, 0); directory.SetColumnSpan(directoryLabel, 2);
            home = new TextBox { Text = Engine.DefaultHome(), ReadOnly = true, Dock = DockStyle.Fill, AccessibleName = "Codex 配置目录", Margin = new Padding(0, 4, 10, 0) };
            browse = new Button { Text = "更改目录…", Dock = DockStyle.Fill, AccessibleName = "更改 Codex 配置目录", Margin = Padding.Empty };
            browse.Click += ChooseHome; directory.Controls.Add(home, 0, 1); directory.Controls.Add(browse, 1, 1); root.Controls.Add(directory, 0, 2);

            Panel feedback = new Panel { Dock = DockStyle.Fill };
            status = new Label { Text = "准备就绪。请先查看预览，再点击安装。", Dock = DockStyle.Fill, Padding = new Padding(0, 13, 0, 0), AccessibleName = "安装状态", AutoEllipsis = false };
            progress = new ProgressBar { Dock = DockStyle.Bottom, Height = 5, Style = ProgressBarStyle.Marquee, Visible = false };
            feedback.Controls.Add(status); feedback.Controls.Add(progress); root.Controls.Add(feedback, 0, 3);

            FlowLayoutPanel buttons = new FlowLayoutPanel { Dock = DockStyle.Fill, FlowDirection = FlowDirection.RightToLeft, WrapContents = false, Padding = new Padding(0, 10, 0, 0) };
            install = new Button { Text = "安装此形象", Size = new Size(156, 38), AccessibleName = "安装小白和小鸡毛", Margin = new Padding(12, 0, 0, 0) };
            close = new Button { Text = "关闭", Size = new Size(88, 38), Margin = new Padding(12, 0, 0, 0) };
            openFolder = new Button { Text = "打开宠物目录", Size = new Size(140, 38), Visible = false, Margin = Padding.Empty };
            install.Click += BeginInstall; close.Click += delegate { Close(); };
            openFolder.Click += delegate { if (installedPath != null) System.Diagnostics.Process.Start("explorer.exe", "\"" + installedPath + "\""); };
            buttons.Controls.Add(install); buttons.Controls.Add(close); buttons.Controls.Add(openFolder); root.Controls.Add(buttons, 0, 4);
            AcceptButton = install; CancelButton = close;
            FormClosing += delegate(object sender, FormClosingEventArgs args) { if (installing) args.Cancel = true; };
        }

        private static Label Body(string text)
        {
            return new Label { Text = text, Dock = DockStyle.Fill, AutoSize = false, Padding = new Padding(0, 8, 0, 0), Margin = Padding.Empty };
        }

        private void ChooseHome(object sender, EventArgs args)
        {
            using (FolderBrowserDialog dialog = new FolderBrowserDialog())
            {
                dialog.Description = "选择 Codex 配置目录（通常名为 .codex），不是程序安装目录。";
                dialog.SelectedPath = home.Text;
                dialog.ShowNewFolderButton = true;
                if (dialog.ShowDialog(this) == DialogResult.OK) home.Text = dialog.SelectedPath;
            }
        }

        private void BeginInstall(object sender, EventArgs args)
        {
            installing = true; install.Enabled = false; browse.Enabled = false; close.Enabled = false; progress.Visible = true;
            status.Text = "正在校验并安装宠物素材…";
            string destination = home.Text;
            BackgroundWorker worker = new BackgroundWorker();
            worker.DoWork += delegate(object s, DoWorkEventArgs e) { e.Result = Engine.Install(destination); };
            worker.RunWorkerCompleted += delegate(object s, RunWorkerCompletedEventArgs e)
            {
                installing = false; progress.Visible = false; close.Enabled = true;
                if (e.Error != null)
                {
                    status.ForeColor = SystemInformation.HighContrast ? SystemColors.WindowText : Color.FromArgb(166, 28, 35);
                    status.Text = "安装未完成：" + e.Error.Message + "\n请检查目录是否可写后重试。";
                    install.Enabled = true; browse.Enabled = true;
                }
                else
                {
                    InstallResult result = (InstallResult)e.Result; installedPath = result.target;
                    status.ForeColor = SystemInformation.HighContrast ? SystemColors.WindowText : Color.FromArgb(31, 99, 50);
                    status.Text = "安装完成。打开 Codex → 设置 → 宠物，刷新后选择“小白和小鸡毛”。" + (result.backup == null ? "" : "\n原版本已保存到 Codex 配置目录的 pet-backups 文件夹。");
                    install.Text = "已安装"; close.Text = "完成"; openFolder.Visible = true;
                }
                worker.Dispose();
            };
            worker.RunWorkerAsync();
        }

        protected override void Dispose(bool disposing)
        {
            if (disposing) { if (preview != null) preview.Dispose(); if (previewStream != null) previewStream.Dispose(); }
            base.Dispose(disposing);
        }
    }
}
