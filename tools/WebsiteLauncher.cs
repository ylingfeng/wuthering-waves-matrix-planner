using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

internal static class WebsiteLauncher
{
    [STAThread]
    private static int Main(string[] args)
    {
        string page = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "web", "index.html");
        if (args.Length == 1 && args[0] == "--check")
            return File.Exists(page) ? 0 : 1;
        try
        {
            if (!File.Exists(page))
                throw new FileNotFoundException("请完整解压，并保留启动器旁的web 文件夹。");
            Process.Start(new ProcessStartInfo(new Uri(page).AbsoluteUri) { UseShellExecute = true });
            return 0;
        }
        catch (Exception error)
        {
            MessageBox.Show("无法打开网页：" + error.Message, "鸣潮矩阵配队", MessageBoxButtons.OK, MessageBoxIcon.Information);
            return 1;
        }
    }
}
