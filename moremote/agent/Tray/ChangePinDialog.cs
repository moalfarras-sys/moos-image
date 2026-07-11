using System.Drawing;
using System.Windows.Forms;

namespace MoRemote;

/// <summary>Owner-side PIN change from the tray (no current PIN required — you're at the machine).</summary>
public sealed class ChangePinDialog : Form
{
    private readonly TextBox _pin = new();
    private readonly TextBox _confirm = new();
    private readonly Label _error = new();

    public string? NewPin { get; private set; }

    public ChangePinDialog()
    {
        Text = "Change PIN";
        FormBorderStyle = FormBorderStyle.FixedDialog;
        StartPosition = FormStartPosition.CenterScreen;
        MaximizeBox = false; MinimizeBox = false;
        ClientSize = new Size(320, 200);
        BackColor = Color.FromArgb(17, 21, 33);
        ForeColor = Color.White;
        Font = new Font("Segoe UI", 9.5f);

        AddLabel("New PIN (min 6 characters)", 16, 16);
        StyleInput(_pin, 16, 38);
        AddLabel("Confirm PIN", 16, 78);
        StyleInput(_confirm, 16, 100);

        _error.ForeColor = Color.FromArgb(248, 113, 113);
        _error.AutoSize = false;
        _error.SetBounds(16, 138, 288, 18);
        _error.Text = "";
        Controls.Add(_error);

        var ok = new Button { Text = "Save", DialogResult = DialogResult.None };
        ok.SetBounds(150, 160, 70, 28);
        StyleButton(ok, Color.FromArgb(59, 130, 246));
        ok.Click += OnSave;

        var cancel = new Button { Text = "Cancel", DialogResult = DialogResult.Cancel };
        cancel.SetBounds(234, 160, 70, 28);
        StyleButton(cancel, Color.FromArgb(55, 60, 80));

        Controls.Add(ok);
        Controls.Add(cancel);
        AcceptButton = ok;
        CancelButton = cancel;
    }

    private void OnSave(object? sender, EventArgs e)
    {
        var p = _pin.Text;
        if (p.Length < 6) { _error.Text = "PIN must be at least 6 characters."; return; }
        if (p != _confirm.Text) { _error.Text = "PINs do not match."; return; }
        NewPin = p;
        DialogResult = DialogResult.OK;
        Close();
    }

    private void AddLabel(string text, int x, int y)
    {
        var l = new Label { Text = text, AutoSize = true, ForeColor = Color.FromArgb(180, 188, 208) };
        l.SetBounds(x, y, 280, 18);
        Controls.Add(l);
    }

    private void StyleInput(TextBox t, int x, int y)
    {
        t.UseSystemPasswordChar = true;
        t.BackColor = Color.FromArgb(30, 35, 52);
        t.ForeColor = Color.White;
        t.BorderStyle = BorderStyle.FixedSingle;
        t.SetBounds(x, y, 288, 26);
        Controls.Add(t);
    }

    private static void StyleButton(Button b, Color color)
    {
        b.FlatStyle = FlatStyle.Flat;
        b.FlatAppearance.BorderSize = 0;
        b.BackColor = color;
        b.ForeColor = Color.White;
        b.Cursor = Cursors.Hand;
    }
}
