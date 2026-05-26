<#
.SYNOPSIS
    Add a directory to the current user's PATH and broadcast the change.

.DESCRIPTION
    Adds -Target to HKCU\Environment\Path (idempotent, preserving %VAR% references
    by keeping the value as REG_EXPAND_SZ), then broadcasts WM_SETTINGCHANGE so the
    shell and newly launched processes pick up the new PATH immediately - without
    having to open the Environment Variables dialog and click Apply.

.PARAMETER Target
    The absolute directory to add to PATH.
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$Target
)

$ErrorActionPreference = 'Stop'

# --- Update the user PATH (raw read so %VAR% references are preserved) ---
$key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey('Environment', $true)
try {
    $path = $key.GetValue('Path', '', [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
    $entries = @($path -split ';' | Where-Object { $_ -ne '' })

    if ($entries -contains $Target) {
        Write-Host "[INFO] Already in PATH: $Target"
    }
    else {
        $newPath = ($entries + $Target) -join ';'
        # ExpandString => REG_EXPAND_SZ, so any %VAR% already in PATH still expands.
        $key.SetValue('Path', $newPath, [Microsoft.Win32.RegistryValueKind]::ExpandString)
        Write-Host "[INFO] Added to PATH: $Target"
    }
}
finally {
    $key.Close()
}

# --- Broadcast WM_SETTINGCHANGE so the change is picked up without a dialog/relogin ---
try {
    $signature = @'
[DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Auto)]
public static extern IntPtr SendMessageTimeout(
    IntPtr hWnd, uint Msg, UIntPtr wParam, string lParam,
    uint fuFlags, uint uTimeout, out UIntPtr lpdwResult);
'@
    $native = Add-Type -MemberDefinition $signature -Name 'NativeMethods' -Namespace 'Win32' -PassThru

    $HWND_BROADCAST   = [IntPtr]0xffff
    $WM_SETTINGCHANGE = 0x1A
    $SMTO_ABORTIFHUNG = 0x2
    $result = [UIntPtr]::Zero

    [void]$native::SendMessageTimeout($HWND_BROADCAST, $WM_SETTINGCHANGE, [UIntPtr]::Zero, 'Environment', $SMTO_ABORTIFHUNG, 5000, [ref]$result)
    Write-Host "[INFO] Broadcasted environment change."
}
catch {
    Write-Host "[WARN] PATH updated, but broadcasting the change failed: $($_.Exception.Message)"
    Write-Host "[WARN] Open a new terminal (or sign out/in) for PATH to take effect."
}

exit 0
