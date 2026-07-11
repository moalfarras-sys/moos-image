using System.Drawing;
using System.Drawing.Drawing2D;
using System.Windows.Forms;

namespace MoRemote;

/// <summary>
/// Always-on-top, non-stealing banner shown whenever a control session is live.
/// This is the visible "someone is controlling this PC" guarantee, with instant
/// Pause / Stop buttons right on it.
/// </summary>
public sealed class SessionBanner : Form
{
    private readonly Label _label = new();
    private readonly Button _pauseBtn = new();
    private readonly Button _stopBtn = new();
    private readonly Action _onStop;
    private readonly Action _onTogglePause;

    public SessionBanner(Action onStop, Action onTogglePause)
    {
        _onStop = onStop;
        _onTogglePause = onTogglePause;

        FormBorderStyle = FormBorderStyle.None;
        StartPosition = FormStartPosition.Manual;
        ShowInTaskbar = false;
        TopMost = true;
        BackColor = Color.FromArgb(24, 28, 40);
        Width = 380;
        Height = 52;
        DoubleBuffered = true;

        var dot = new Panel { Width = 12, Height = 12, Left = 16, Top = 20, BackColor = Color.FromArgb(239, 68, 68) };
        MakeCircular(dot);

        _label.AutoSize = false;
        _label.Left = 36; _label.Top = 0; _label.Width = 210; _label.Height = Height;
        _label.TextAlign = ContentAlignment.MiddleLeft;
        _label.ForeColor = Color.White;
        _label.Font = new Font("Segoe UI", 9.5f, FontStyle.Bold);
        _label.Text = "Remote control active";

        StyleButton(_pauseBtn, "Pause", Color.FromArgb(59, 66, 92));
        _pauseBtn.Left = 250; _pauseBtn.Top = 11; _pauseBtn.Width = 58; _pauseBtn.Height = 30;
        _pauseBtn.Click += (_, _) => _onTogglePause();

        StyleButton(_stopBtn, "Stop", Color.FromArgb(220, 38, 38));
        _stopBtn.Left = 312; _stopBtn.Top = 11; _stopBtn.Width = 54; _stopBtn.Height = 30;
        _stopBtn.Click += (_, _) => _onStop();

        Controls.Add(dot);
        Controls.Add(_label);
        Controls.Add(_pauseBtn);
        Controls.Add(_stopBtn);
    }

    public void UpdateState(int activeCount, bool paused, string remotes)
    {
        _label.Text = paused
            ? $"Session PAUSED · {activeCount} device(s)"
            : $"Remote control active · {remotes}";
        _pauseBtn.Text = paused ? "Resume" : "Pause";
        _pauseBtn.BackColor = paused ? Color.FromArgb(34, 197, 94) : Color.FromArgb(59, 66, 92);
        Reposition();
    }

    public void Reposition()
    {
        var wa = Screen.PrimaryScreen?.WorkingArea ?? new Rectangle(0, 0, 1280, 720);
        Left = wa.Left + (wa.Width - Width) / 2;
        Top = wa.Top + 10;
    }

    // Don't steal focus from whatever the remote user is doing.
    protected override bool ShowWithoutActivation => true;
    protected override CreateParams CreateParams
    {
        get
        {
            const int WS_EX_TOOLWINDOW = 0x00000080;
            const int WS_EX_NOACTIVATE = 0x08000000;
            const int WS_EX_TOPMOST = 0x00000008;
            var cp = base.CreateParams;
            cp.ExStyle |= WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_TOPMOST;
            return cp;
        }
    }

    private static void StyleButton(Button b, string text, Color color)
    {
        b.Text = text;
        b.FlatStyle = FlatStyle.Flat;
        b.FlatAppearance.BorderSize = 0;
        b.BackColor = color;
        b.ForeColor = Color.White;
        b.Font = new Font("Segoe UI", 9f, FontStyle.Bold);
        b.Cursor = Cursors.Hand;
        b.TabStop = false;
    }

    private static void MakeCircular(Control c)
    {
        using var path = new GraphicsPath();
        path.AddEllipse(0, 0, c.Width, c.Height);
        c.Region = new Region(path);
    }
}
