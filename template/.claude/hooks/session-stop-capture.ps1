<#
.SYNOPSIS
Claude Code Stop Event Hook (PowerShell Versiyonu).

.DESCRIPTION
Oturum tamamlandığında (Stop event) devreye girer.
Oturumda dosya düzenleme, kod yazma veya mutasyon yaratan kabuk çalışması
varsa Claude'a stderr üzerinden bildirim yollar ve Last-Session.md ile günün logunu
güncellemesini tetikler.

Sonsuz döngüyü engellemek için atomik dizin kilidi kullanır.
Salt-okunur (read-only) oturumlarda sessizce sonlanır (Exit 0).
#>

[Console]::InputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$InputData = [Console]::In.ReadToEnd()
if ([string]::IsNullOrWhiteSpace($InputData)) {
    exit 0
}

try {
    $Payload = $InputData | ConvertFrom-Json
} catch {
    exit 0
}

# 1. Sonsuz döngü kontrolü
if ($Payload.stop_hook_active -eq $true) {
    exit 0
}

$SessionId = $Payload.session_id
if ([string]::IsNullOrWhiteSpace($SessionId)) {
    $SessionId = "default_session"
}

# 2. Oturum başına 1 kez çalışma kilidi (Sentinel)
$SentinelDir = [System.IO.Path]::Combine([System.Environment]::GetFolderPath('UserProfile'), ".respectedos", "hooks", "sentinels")
if (-not (Test-Path $SentinelDir)) {
    New-Item -ItemType Directory -Path $SentinelDir -Force | Out-Null
}

$SessionLock = [System.IO.Path]::Combine($SentinelDir, $SessionId)
if (Test-Path $SessionLock) {
    exit 0
}

# 3. Transkriptte mutasyon kontrolü
$TranscriptPath = $Payload.transcript_path
$HasMutations = $false

if ($TranscriptPath -and (Test-Path $TranscriptPath)) {
    $TranscriptContent = Get-Content -Path $TranscriptPath -Raw -ErrorAction SilentlyContinue
    if ($TranscriptContent) {
        # Dosya yazma veya değiştirme araçları kullanılmış mı?
        $MutatingKeywords = @("write_to_file", "replace_file_content", "multi_replace_file_content", "git commit", "npm install", "pip install")
        foreach ($kw in $MutatingKeywords) {
            if ($TranscriptContent -match [regex]::Escape($kw)) {
                $HasMutations = $true
                break
            }
        }
    }
} else {
    # Transkript yolu yoksa genel kontrole bak
    if ($Payload.tool_calls) {
        $HasMutations = $true
    }
}

if (-not $HasMutations) {
    # Salt okunur oturum; hafıza tetiklemeye gerek yok
    exit 0
}

# Kilidi oluştur (atomik)
New-Item -ItemType Directory -Path $SessionLock -Force | Out-Null

# Claude'u uyandır: stderr üzerinden exit code 2
$PromptMessage = @"
[RESPECTED-OS HAFIZA SİSTEMİ BİLDİRİMİ]
Bu oturumda anlamlı kod/dosya değişiklikleri yapıldı.
Oturumu kapatmadan önce lütfen:
1. '🔮 850-Companion/Last-Session.md' dosyasını güncelle.
2. Açık veya tamamlanan işleri 'Threads.md' veya günün 'daily/YYYY-MM-DD.md' loguna kısaca işle.
Hafıza devrini tamamladıktan sonra oturumu sonlandır.
"@

[Console]::Error.WriteLine($PromptMessage)
exit 2
