Option Explicit
Dim fs, root, script, shell, command
Set fs = CreateObject("Scripting.FileSystemObject")
root = fs.GetParentFolderName(WScript.ScriptFullName)
If Not fs.FileExists(fs.BuildPath(root, "agent\ad_settings.ps1")) Then
    root = fs.GetParentFolderName(root)
End If
script = fs.BuildPath(root, "agent\ad_settings.ps1")
If Not fs.FileExists(script) Then
    MsgBox "MaaNekoConnect settings component is missing.", 16, "Advertisement AI"
    WScript.Quit 1
End If
Set shell = CreateObject("WScript.Shell")
command = """" & shell.ExpandEnvironmentStrings("%SystemRoot%") & "\System32\WindowsPowerShell\v1.0\powershell.exe"" -NoProfile -STA -ExecutionPolicy Bypass -File """ & script & """"
shell.Run command, 0, True
