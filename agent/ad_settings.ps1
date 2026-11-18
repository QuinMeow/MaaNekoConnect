$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName PresentationFramework
Add-Type -AssemblyName System.Security
$root = Split-Path -Parent $PSScriptRoot
$configPath = Join-Path $root 'config\ad_ai.dat'
$savedKey = ''
$savedEnabled = $false
$savedModel = 'deepseek-v4-flash'
if (Test-Path -LiteralPath $configPath) {
    try {
        $saved = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $savedKey = [string]$saved.protected_key
        $savedEnabled = $saved.enabled -eq $true
        $savedModel = [string]$saved.model
    } catch {
        [System.Windows.MessageBox]::Show('Existing settings could not be read. They will not be changed unless you save.', 'MaaNekoConnect') | Out-Null
    }
}
[xml]$xaml = @'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        Title="MaaNekoConnect - Advertisement AI" Width="570" Height="430"
        WindowStartupLocation="CenterScreen" ResizeMode="NoResize" Background="#FFF7EC">
 <StackPanel Margin="28">
  <TextBlock FontSize="25" FontWeight="Bold" Text="DeepSeek advertisement close"/>
  <TextBlock Margin="0,10,0,18" TextWrapping="Wrap"
    Text="Only wait and close. Never play, install, purchase or open the store. Four corner crops are sent to DeepSeek; API charges may apply."/>
  <CheckBox Name="Enabled" Content="Enable AI close (upload corner crops)" Margin="0,0,0,14"/>
  <TextBlock Text="Official endpoint: https://api.deepseek.com/chat/completions"/>
  <TextBlock Text="Model" Margin="0,12,0,4"/>
  <TextBox Name="Model" Height="30"/>
  <TextBlock Name="KeyLabel" Text="API Key" Margin="0,12,0,4"/>
  <PasswordBox Name="Key" Height="30"/>
  <TextBlock Name="Status" Margin="0,8,0,8" TextWrapping="Wrap" Foreground="#874B22"/>
  <StackPanel Orientation="Horizontal" HorizontalAlignment="Right">
   <Button Name="Cancel" Content="Cancel" Width="90" Margin="0,0,10,0"/>
   <Button Name="Save" Content="Save" Width="90"/>
  </StackPanel>
 </StackPanel>
</Window>
'@
$window = [Windows.Markup.XamlReader]::Load((New-Object Xml.XmlNodeReader $xaml))
$enabled = $window.FindName('Enabled')
$model = $window.FindName('Model')
$key = $window.FindName('Key')
$status = $window.FindName('Status')
$enabled.IsChecked = $savedEnabled
$model.Text = $savedModel
if ($savedKey) { $window.FindName('KeyLabel').Text = 'API Key (saved; leave blank to keep)' }
$window.FindName('Cancel').Add_Click({ $window.Close() })
$window.FindName('Save').Add_Click({
    try {
        $protected = $savedKey
        if ($key.Password) {
            $bytes = [Text.Encoding]::UTF8.GetBytes($key.Password.Trim())
            try {
                $protected = [Convert]::ToBase64String([Security.Cryptography.ProtectedData]::Protect(
                    $bytes, $null, [Security.Cryptography.DataProtectionScope]::CurrentUser))
            } finally { [Array]::Clear($bytes, 0, $bytes.Length) }
        }
        if ($enabled.IsChecked -and (-not $protected -or -not $model.Text.Trim())) {
            $status.Text = 'Enter an API Key and model before enabling.'
            return
        }
        $settings = [ordered]@{ version = 1; enabled = [bool]$enabled.IsChecked
            endpoint = 'https://api.deepseek.com/chat/completions'
            model = $model.Text.Trim(); protected_key = $protected }
        $directory = Split-Path -Parent $configPath
        [IO.Directory]::CreateDirectory($directory) | Out-Null
        $temporary = Join-Path $directory ([Guid]::NewGuid().ToString() + '.tmp')
        try {
            [IO.File]::WriteAllText($temporary, ($settings | ConvertTo-Json), (New-Object Text.UTF8Encoding $false))
            if (Test-Path -LiteralPath $configPath) {
                [IO.File]::Replace($temporary, $configPath, $null)
            } else { [IO.File]::Move($temporary, $configPath) }
        } finally {
            if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary }
        }
        $key.Clear()
        $window.Close()
    } catch { $status.Text = 'Could not save settings. Check access to the local config folder.' }
})
$window.ShowDialog() | Out-Null
