$ErrorActionPreference = "Stop"

function Set-EnvVar {
    Param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    [Environment]::SetEnvironmentVariable($Name, $Value, "User")
    Set-Item -Path "Env:$Name" -Value $Value
}

function Read-OptionalValue {
    Param(
        [Parameter(Mandatory = $true)]
        [string]$Prompt
    )

    $value = Read-Host $Prompt
    if ([string]::IsNullOrWhiteSpace($value)) {
        return $null
    }

    return $value.Trim()
}

function Read-PasswordValue {
    Param(
        [Parameter(Mandatory = $true)]
        [string]$Prompt
    )

    $secure = Read-Host $Prompt -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }

    if ([string]::IsNullOrWhiteSpace($plain)) {
        return $null
    }

    return $plain
}

Write-Host "=============================================="
Write-Host "GlassOrchestrator Environment Setup"
Write-Host "=============================================="
Write-Host "Enter values to set them. Press Enter to skip."
Write-Host "Values are saved to User environment variables."
Write-Host ""

$username = Read-OptionalValue -Prompt "GLASS_LOGIN_USERNAME"
if ($null -ne $username) {
    Set-EnvVar -Name "GLASS_LOGIN_USERNAME" -Value $username
}

$password = Read-PasswordValue -Prompt "GLASS_LOGIN_PASSWORD"
if ($null -ne $password) {
    Set-EnvVar -Name "GLASS_LOGIN_PASSWORD" -Value $password
}

$loginId = Read-OptionalValue -Prompt "GLASS_LOGIN_ID"
if ($null -ne $loginId) {
    Set-EnvVar -Name "GLASS_LOGIN_ID" -Value $loginId
}

Write-Host ""
Write-Host "Environment status in this terminal:"
Write-Host ("GLASS_LOGIN_USERNAME set: {0}" -f (-not [string]::IsNullOrWhiteSpace($env:GLASS_LOGIN_USERNAME)))
Write-Host ("GLASS_LOGIN_PASSWORD set: {0}" -f (-not [string]::IsNullOrWhiteSpace($env:GLASS_LOGIN_PASSWORD)))
Write-Host ("GLASS_LOGIN_ID set: {0}" -f (-not [string]::IsNullOrWhiteSpace($env:GLASS_LOGIN_ID)))

Write-Host ""
Write-Host "Done. Open a new terminal to pick up persisted values globally."
