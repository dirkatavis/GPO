$ErrorActionPreference = "Stop"

$securePassword = Read-Host "Enter GLASS_LOGIN_PASSWORD" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
try {
    $plainPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
}
finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}

if ([string]::IsNullOrWhiteSpace($plainPassword)) {
    Write-Error "GLASS_LOGIN_PASSWORD was empty. Nothing was changed."
    exit 1
}

# Persist for this user profile.
[Environment]::SetEnvironmentVariable("GLASS_LOGIN_PASSWORD", $plainPassword, "User")

# Also set immediately for the current terminal session.
Set-Item -Path "Env:GLASS_LOGIN_PASSWORD" -Value $plainPassword

Write-Host "GLASS_LOGIN_PASSWORD set for current session and persisted for the current user."
Write-Host ("GLASS_LOGIN_PASSWORD set now: {0}" -f (-not [string]::IsNullOrWhiteSpace($env:GLASS_LOGIN_PASSWORD)))
