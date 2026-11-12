// Public local test controls, with no authentication, submission or persistence.
using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Windows.Forms;

sealed class FieldProbe : Form {
    FieldProbe() {
        Text = "Saydraft field probe - " + Process.GetCurrentProcess().Id;
        ClientSize = new Size(600, 210);
        StartPosition = FormStartPosition.CenterScreen;
        var description = new Label { Text = "Public local fixtures. Select a field, then tap F9 twice.",
            Location = new Point(18, 16), AutoSize = true };
        var passwordLabel = new Label { Text = "Empty password-style test field", Location = new Point(18, 47), AutoSize = true };
        var password = new TextBox { Name = "passwordFixture", AccessibleName = "Empty password-style fixture",
            UseSystemPasswordChar = true, Location = new Point(18, 68), Width = 560, TabIndex = 0 };
        var plainLabel = new Label { Text = "Public plain test field", Location = new Point(18, 105), AutoSize = true };
        var plain = new TextBox { Name = "plainFixture", AccessibleName = "Public plain fixture",
            Text = "Public plain fixture", Location = new Point(18, 126), Width = 560, TabIndex = 1 };
        var status = new Label { Location = new Point(18, 170), AutoSize = true };
        password.Enter += delegate { status.Text = "Password-style fixture focused"; };
        plain.Enter += delegate { status.Text = "Public plain fixture focused"; };
        Controls.AddRange(new Control[] { description, passwordLabel, password, plainLabel, plain, status });
        Shown += delegate {
            password.Focus();
            File.WriteAllText(Path.ChangeExtension(Application.ExecutablePath, ".pid"),
                              Process.GetCurrentProcess().Id.ToString());
        };
    }

    [STAThread]
    static void Main() {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        Application.Run(new FieldProbe());
    }
}
