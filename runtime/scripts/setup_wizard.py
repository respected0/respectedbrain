#!/usr/bin/env python3
"""Respected Brain — Tek Tık Windows Kurulum, Bakım & Yönetim Sihirbazı (GUI).

Zero-dependency Windows Tkinter arayüzü ile:
  - Mevcut kurulumu otomatik tespit eder
  - Otomatik güncelleme (Auto-Update) onayı ve hızlı güncelleme
  - Profesyonel Bakım Modları: Güncelle (Update), Onar (Repair), Değiştir (Modify), Kaldır (Uninstall)
  - Python CLI eşdeğeri sorular: Kullanıcı Adı, Companion, Birincil AI Model Seçimi
  - Masaüstü kısayolları, Windows Görev Zamanlayıcı (08:00 brifingi), Global AI kuralları ve MCP Sunucu kaydı
  - Web Gateway'i (localhost:8520) başlatır
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk

if getattr(sys, "frozen", False):
    EXE_DIR = Path(sys.executable).resolve().parent
    if (EXE_DIR / "update.py").is_file():
        REPO_ROOT = EXE_DIR
    elif (EXE_DIR.parent / "update.py").is_file():
        REPO_ROOT = EXE_DIR.parent
    else:
        REPO_ROOT = EXE_DIR
    SCRIPT_DIR = (REPO_ROOT / "runtime" / "scripts") if (REPO_ROOT / "runtime" / "scripts").is_dir() else (REPO_ROOT / "scripts")
else:
    SCRIPT_DIR = Path(__file__).resolve().parent
    REPO_ROOT = SCRIPT_DIR.parent.parent if SCRIPT_DIR.parent.name == "runtime" else SCRIPT_DIR.parent

DEFAULT_VAULT = Path.home() / "Documents" / "RespectedOS"


def _find_system_python() -> str:
    """Find the actual python interpreter on the system."""
    for cmd in ["py.exe", "python.exe", "python3.exe", "py", "python"]:
        found = shutil.which(cmd)
        if found and not found.lower().endswith("setup.exe"):
            return found
    local_py = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Python"
    if local_py.is_dir():
        for exe in local_py.glob("**/python.exe"):
            if exe.is_file():
                return str(exe)
    return "python"


class SetupWizard:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Respected Brain v0.0.1 — Kurulum & Bakım Sihirbazı")
        self.root.geometry("680x640")
        self.root.resizable(False, False)
        self.root.configure(bg="#0d1117")

        self.vault_path_var = tk.StringVar(value=str(DEFAULT_VAULT))
        self.user_name_var = tk.StringVar(value=os.environ.get("USERNAME", "Furkan"))
        self.companion_var = tk.StringVar(value="Jarvis")
        self.model_choice_var = tk.StringVar(value="auto")
        self.mode_var = tk.StringVar(value="install")  # install, update, repair, modify, uninstall

        self.desktop_shortcut_var = tk.BooleanVar(value=True)
        self.schedule_var = tk.BooleanVar(value=True)
        self.global_rules_var = tk.BooleanVar(value=True)
        self.mcp_server_var = tk.BooleanVar(value=True)

        self._build_ui()
        self._check_prerequisites()
        self.root.after(200, self._detect_and_prompt_existing)

    def _build_ui(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TLabel", background="#0d1117", foreground="#c9d1d9", font=("Segoe UI", 10))
        style.configure("Header.TLabel", background="#0d1117", foreground="#58a6ff", font=("Segoe UI", 15, "bold"))
        style.configure("SubHeader.TLabel", background="#0d1117", foreground="#8b949e", font=("Segoe UI", 9))
        style.configure("Card.TFrame", background="#161b22")
        style.configure("TRadiobutton", background="#161b22", foreground="#c9d1d9", font=("Segoe UI", 9))
        style.configure("TCheckbutton", background="#161b22", foreground="#c9d1d9", font=("Segoe UI", 9))

        # Header
        header_frame = tk.Frame(self.root, bg="#0d1117", padx=20, pady=12)
        header_frame.pack(fill="x")

        title = ttk.Label(header_frame, text="⚡ Respected Brain v0.0.1 Kurulum & Yönetim", style="Header.TLabel")
        title.pack(anchor="w")
        desc = ttk.Label(
            header_frame,
            text="İkinci Beyin & Yapay Zeka Model Router Altyapısı (v0.0.1)",
            style="SubHeader.TLabel",
        )
        desc.pack(anchor="w", pady=(1, 0))

        # Body Container
        card = tk.Frame(self.root, bg="#161b22", padx=16, pady=12, highlightbackground="#30363d", highlightthickness=1)
        card.pack(fill="both", expand=True, padx=20, pady=2)

        # Status box
        self.status_box = tk.Text(
            card,
            height=4,
            bg="#090d13",
            fg="#58a6ff",
            font=("Consolas", 8),
            relief="flat",
            padx=8,
            pady=6,
            highlightbackground="#30363d",
            highlightthickness=1,
        )
        self.status_box.pack(fill="x", pady=(0, 8))
        self.status_box.insert("end", "[*] Respected Brain altyapısı başlatılıyor...\n")
        self.status_box.configure(state="disabled")

        # 1. Operation Mode Frame
        mode_frame = tk.LabelFrame(card, text=" İşlem Modu ", bg="#161b22", fg="#58a6ff", font=("Segoe UI", 9, "bold"), padx=8, pady=4)
        mode_frame.pack(fill="x", pady=(0, 8))

        modes = [
            ("🔄 Güncelle (Update)", "update"),
            ("🛠️ Onar (Repair)", "repair"),
            ("⚙️ Değiştir (Modify)", "modify"),
            ("🚀 Temiz Kurulum", "install"),
            ("🗑️ Kaldır (Uninstall)", "uninstall"),
        ]
        for text, val in modes:
            r = tk.Radiobutton(
                mode_frame,
                text=text,
                value=val,
                variable=self.mode_var,
                command=self._on_mode_change,
                bg="#161b22",
                fg="#f0f6fc",
                selectcolor="#090d13",
                activebackground="#161b22",
                activeforeground="#58a6ff",
                font=("Segoe UI", 9),
            )
            r.pack(side="left", padx=4)

        # 2. Vault Path Frame
        path_frame = tk.Frame(card, bg="#161b22")
        path_frame.pack(fill="x", pady=(0, 8))

        vault_label = tk.Label(path_frame, text="Kasa (Vault) Yolu:", bg="#161b22", fg="#c9d1d9", font=("Segoe UI", 9, "bold"))
        vault_label.pack(side="left")

        self.path_entry = tk.Entry(
            path_frame,
            textvariable=self.vault_path_var,
            bg="#090d13",
            fg="#f0f6fc",
            font=("Segoe UI", 9),
            relief="flat",
            highlightbackground="#30363d",
            highlightthickness=1,
        )
        self.path_entry.pack(side="left", fill="x", expand=True, ipady=2, padx=(8, 8))

        browse_btn = tk.Button(
            path_frame,
            text="Gözat...",
            command=self._browse_vault,
            bg="#21262d",
            fg="#c9d1d9",
            relief="flat",
            font=("Segoe UI", 8),
            padx=8,
        )
        browse_btn.pack(side="right")

        # 3. User & Companion Profile Frame
        self.profile_frame = tk.LabelFrame(card, text=" Kullanıcı & Companion Profili ", bg="#161b22", fg="#58a6ff", font=("Segoe UI", 9, "bold"), padx=8, pady=4)
        self.profile_frame.pack(fill="x", pady=(0, 8))

        u_label = tk.Label(self.profile_frame, text="Hitap Şekli / Adınız:", bg="#161b22", fg="#c9d1d9", font=("Segoe UI", 9))
        u_label.grid(row=0, column=0, sticky="w", pady=2)
        u_entry = tk.Entry(self.profile_frame, textvariable=self.user_name_var, bg="#090d13", fg="#f0f6fc", width=22, relief="flat", highlightbackground="#30363d", highlightthickness=1)
        u_entry.grid(row=0, column=1, sticky="w", padx=(6, 20), pady=2)

        c_label = tk.Label(self.profile_frame, text="Companion Adı:", bg="#161b22", fg="#c9d1d9", font=("Segoe UI", 9))
        c_label.grid(row=0, column=2, sticky="w", pady=2)
        c_entry = tk.Entry(self.profile_frame, textvariable=self.companion_var, bg="#090d13", fg="#f0f6fc", width=22, relief="flat", highlightbackground="#30363d", highlightthickness=1)
        c_entry.grid(row=0, column=3, sticky="w", padx=6, pady=2)

        # 4. AI Model & Fallback Priority Frame
        self.model_frame = tk.LabelFrame(card, text=" Birincil AI Model ve Router Tercihi ", bg="#161b22", fg="#58a6ff", font=("Segoe UI", 9, "bold"), padx=8, pady=4)
        self.model_frame.pack(fill="x", pady=(0, 8))

        models = [
            ("⚡ Akıllı Otomatik (Auto — Önerilen)", "auto"),
            ("🪐 Google Antigravity", "antigravity"),
            ("🧠 OpenAI Codex", "codex"),
            ("🎭 Anthropic Claude", "claude"),
            ("✨ Google Gemini", "gemini"),
        ]
        for text, val in models:
            r = tk.Radiobutton(
                self.model_frame,
                text=text,
                value=val,
                variable=self.model_choice_var,
                bg="#161b22",
                fg="#c9d1d9",
                selectcolor="#090d13",
                activebackground="#161b22",
                font=("Segoe UI", 9),
            )
            r.pack(anchor="w", pady=1)

        # 5. Tasks / Integrations Frame
        self.tasks_frame = tk.LabelFrame(card, text=" Sistem Entegrasyonları ve Otomasyon ", bg="#161b22", fg="#58a6ff", font=("Segoe UI", 9, "bold"), padx=8, pady=4)
        self.tasks_frame.pack(fill="x", pady=(0, 4))

        chk1 = tk.Checkbutton(self.tasks_frame, text="Masaüstüne Kontrol Paneli kısayolu ekle", variable=self.desktop_shortcut_var, bg="#161b22", fg="#c9d1d9", selectcolor="#090d13", activebackground="#161b22", font=("Segoe UI", 9))
        chk1.pack(anchor="w", pady=1)

        chk2 = tk.Checkbutton(self.tasks_frame, text="Her sabah 08:00'de otomatik sabah brifingi zamanla (Windows Görev Zamanlayıcı)", variable=self.schedule_var, bg="#161b22", fg="#c9d1d9", selectcolor="#090d13", activebackground="#161b22", font=("Segoe UI", 9))
        chk2.pack(anchor="w", pady=1)

        chk3 = tk.Checkbutton(self.tasks_frame, text="Global AI kurallarına (~/.gemini, ~/.claude vb.) bağla", variable=self.global_rules_var, bg="#161b22", fg="#c9d1d9", selectcolor="#090d13", activebackground="#161b22", font=("Segoe UI", 9))
        chk3.pack(anchor="w", pady=1)

        chk4 = tk.Checkbutton(self.tasks_frame, text="Dış editörler için MCP Sunucusunu kaydet (Claude Desktop, Cursor, Antigravity)", variable=self.mcp_server_var, bg="#161b22", fg="#c9d1d9", selectcolor="#090d13", activebackground="#161b22", font=("Segoe UI", 9))
        chk4.pack(anchor="w", pady=1)

        # Progress bar
        self.progress = ttk.Progressbar(card, mode="indeterminate")
        self.progress.pack(fill="x", pady=(8, 4))

        # Footer Actions
        footer = tk.Frame(self.root, bg="#0d1117", padx=20, pady=10)
        footer.pack(fill="x")

        self.btn_action = tk.Button(
            footer,
            text="🚀 Başlat",
            command=self._start_action_thread,
            bg="#238636",
            fg="#ffffff",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padx=20,
            pady=6,
            cursor="hand2",
        )
        self.btn_action.pack(side="right")

    def _log(self, text: str) -> None:
        self.status_box.configure(state="normal")
        self.status_box.insert("end", text + "\n")
        self.status_box.see("end")
        self.status_box.configure(state="disabled")

    def _browse_vault(self) -> None:
        from tkinter import filedialog
        chosen = filedialog.askdirectory(initialdir=str(Path.home() / "Documents"), title="Vault Dizinini Seçin")
        if chosen:
            self.vault_path_var.set(chosen)
            self._check_target_status()

    def _check_prerequisites(self) -> None:
        py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        self._log(f"[✓] Python: v{py_ver}")
        git_cmd = shutil.which("git")
        if git_cmd:
            self._log("[✓] Git: Mevcut")
        else:
            self._log("[!] Git sistemde bulunamadı.")

        tools = {"Antigravity": "agy", "Gemini": "gemini", "Claude": "claude", "Codex": "codex"}
        installed = [name for name, cmd in tools.items() if shutil.which(cmd) or shutil.which(f"{cmd}.cmd") or shutil.which(f"{cmd}.exe")]
        self._log(f"[+] Algılanan AI CLI Araçları: {', '.join(installed) if installed else 'Henüz CLI aracı eklenmemiş'}")

    def _detect_and_prompt_existing(self) -> None:
        vault_path = Path(self.vault_path_var.get().strip()).resolve()
        if (vault_path / ".respectedbrain-version").is_file() or (vault_path / ".beyin").is_dir():
            self._log(f"[!] Mevcut Respected Brain kasası tespit edildi: {vault_path}")
            self.mode_var.set("update")
            self._on_mode_change()

            ans = messagebox.askyesnocancel(
                "Respected Brain Kurulum Tespiti",
                f"Sisteminizde mevcut bir Respected Brain kasası tespit edildi:\n{vault_path}\n\n"
                "Yeni sürüme (v0.0.1) doğrudan HIZLI GÜNCELLEME yapmak istiyor musunuz?\n" +
                "(Kişisel notlarınız, şablonlarınız ve hafızanız korunacaktır)\n\n" +
                "[Evet]: Hızlı Güncelleme\n" +
                "[Hayır]: Bakım Menüsü (Değiştir / Onar / Kaldır)\n" +
                "[İptal]: Kapat",
            )
            if ans is True:
                # Fast track update
                self.mode_var.set("update")
                self._on_mode_change()
                self._start_action_thread()
            elif ans is False:
                # Open maintenance mode
                self.mode_var.set("update")
                self._on_mode_change()
            elif ans is None:
                self.root.destroy()

    def _check_target_status(self) -> None:
        vault_path = Path(self.vault_path_var.get().strip()).resolve()
        if (vault_path / ".respectedbrain-version").is_file() or (vault_path / ".beyin").is_dir():
            self.mode_var.set("update")
        else:
            self.mode_var.set("install")
        self._on_mode_change()

    def _on_mode_change(self) -> None:
        mode = self.mode_var.get()
        if mode == "update":
            self.btn_action.configure(text="🔄 Kasayı Güncelle", bg="#1f6feb")
        elif mode == "repair":
            self.btn_action.configure(text="🛠️ Kasayı Onar", bg="#d29922")
        elif mode == "modify":
            self.btn_action.configure(text="⚙️ Ayarları Kaydet", bg="#8957e5")
        elif mode == "uninstall":
            self.btn_action.configure(text="🗑️ Kaldır", bg="#da3633")
        else:
            self.btn_action.configure(text="🚀 Tek Tıkla Kur", bg="#238636")

    def _start_action_thread(self) -> None:
        self.btn_action.configure(state="disabled")
        self.progress.start(10)
        t = threading.Thread(target=self._run_action, daemon=True)
        t.start()

    def _run_action(self) -> None:
        mode = self.mode_var.get()
        vault_path = Path(self.vault_path_var.get().strip()).resolve()
        py_bin = _find_system_python()

        try:
            if mode == "uninstall":
                self._run_uninstall(vault_path)
            elif mode == "repair":
                self._run_repair(py_bin, vault_path)
            elif mode == "update":
                self._run_update(py_bin, vault_path)
            elif mode in ("modify", "install"):
                self._run_install_or_modify(py_bin, vault_path)

        except Exception as e:
            self._log(f"[!] Hata oluştu: {e}")
            messagebox.showerror("Hata", str(e))
            self._finish(False)

    def _run_uninstall(self, vault_path: Path) -> None:
        if not messagebox.askyesno(
            "Kaldırma Onayı",
            f"Respected Brain zamanlanmış görevleri ve kısayolları sistemden kaldırılacaktır.\n\n"
            f"Kasanız ({vault_path}) ve notlarınız KESİNLİKLE SİLİNMEZ.\n\n"
            "Devam etmek istiyor musunuz?",
        ):
            self._finish(False)
            return

        self._log("[*] Zamanlanmış sabah brifingi görevi siliniyor...")
        subprocess.run(["schtasks", "/Delete", "/TN", "RespectedBrainBriefing", "/F"], capture_output=True)
        subprocess.run(["schtasks", "/Delete", "/TN", "respected-morning-briefing-*", "/F"], capture_output=True)

        self._log("[*] Masaüstü kısayolları kaldırılıyor...")
        desktop = Path.home() / "Desktop"
        if desktop.is_dir():
            (desktop / "Respected Brain Gateway.url").unlink(missing_ok=True)
            (desktop / "RespectedOS.url").unlink(missing_ok=True)

        self._log("[✓] Respected Brain başarıyla sistemden kaldırıldı.")
        messagebox.showinfo("Kaldırma Tamamlandı", "Respected Brain servisleri ve kısayolları başarıyla kaldırıldı.")
        self._finish(True)

    def _run_repair(self, py_bin: str, vault_path: Path) -> None:
        self._log(f"[*] Onarım başlatılıyor: {vault_path}")
        update_cmd = [
            py_bin,
            str(SCRIPT_DIR / "update_respected.py"),
            str(vault_path),
            "--platform", "windows-native",
            "--force",
            "--apply",
        ]
        proc = subprocess.run(update_cmd, cwd=REPO_ROOT, capture_output=True, text=True)
        if proc.returncode != 0:
            self._log(f"[!] Onarım hatası: {proc.stderr}")
            messagebox.showerror("Onarım Hatası", proc.stderr)
            self._finish(False)
            return

        if self.global_rules_var.get():
            self._log("[*] Global AI kuralları ve kancaları onarılıyor...")
            subprocess.run([
                py_bin,
                str(SCRIPT_DIR / "install_global.py"),
                str(vault_path),
                "--platform", "windows-native",
                "--apply",
            ], capture_output=True)

        self._log("[✓] Onarım başarıyla tamamlandı!")
        messagebox.showinfo("Başarılı", "Respected Brain bileşenleri ve şablonları başarıyla onarıldı.")
        self._finish(True)

    def _run_update(self, py_bin: str, vault_path: Path) -> None:
        self._log(f"[*] Hızlı güncelleme başlatılıyor: {vault_path}")
        cmd = [
            py_bin,
            str(REPO_ROOT / "update.py"),
            str(vault_path),
            "--apply",
            "--platform", "windows-native",
            "--force",
        ]
        proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
        if proc.returncode != 0:
            self._log(f"[!] Güncelleme hatası: {proc.stderr}")
            messagebox.showerror("Güncelleme Hatası", proc.stderr)
            self._finish(False)
            return

        self._log("[✓] Çekirdek motorlar ve yetenekler güncellendi.")
        self._post_install(py_bin, vault_path)

    def _run_install_or_modify(self, py_bin: str, vault_path: Path) -> None:
        self._log(f"[*] Yapılandırma uygulanıyor: {vault_path}")

        priority_map = {
            "auto": ["claude", "codex", "gemini", "antigravity", "cursor"],
            "antigravity": ["antigravity", "gemini", "codex", "claude", "cursor"],
            "codex": ["codex", "claude", "gemini", "antigravity", "cursor"],
            "claude": ["claude", "codex", "gemini", "antigravity", "cursor"],
            "gemini": ["gemini", "codex", "claude", "antigravity", "cursor"],
        }
        chosen_model = self.model_choice_var.get()
        priority_list = priority_map.get(chosen_model, priority_map["auto"])

        cmd = [
            py_bin,
            str(REPO_ROOT / "install.py"),
            str(vault_path),
            "--non-interactive",
            "--user-name", self.user_name_var.get().strip() or "Furkan",
            "--companion", self.companion_var.get().strip() or "Jarvis",
            "--provider", "auto",
            "--priority", *priority_list,
        ]

        if self.desktop_shortcut_var.get():
            cmd.append("--desktop-shortcut")
        else:
            cmd.append("--no-desktop-shortcut")

        if self.schedule_var.get():
            cmd.extend(["--install-schedule", "--schedule-time", "08:00"])
        else:
            cmd.append("--no-install-schedule")

        if self.global_rules_var.get():
            cmd.append("--install-global")

        if self.mcp_server_var.get():
            cmd.append("--install-mcp")
        else:
            cmd.append("--no-install-mcp")

        proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
        if proc.returncode != 0:
            self._log(f"[!] Kurulum hatası: {proc.stderr}")
            messagebox.showerror("Kurulum Hatası", proc.stderr)
            self._finish(False)
            return

        self._log("[✓] Respected Brain başarıyla yapılandırıldı.")
        self._post_install(py_bin, vault_path)

    def _post_install(self, py_bin: str, vault_path: Path) -> None:
        # Desktop Gateway URL
        if self.desktop_shortcut_var.get():
            desktop = Path.home() / "Desktop"
            if desktop.is_dir():
                url_file = desktop / "Respected Brain Gateway.url"
                url_file.write_text("[InternetShortcut]\nURL=http://localhost:8520\nIconIndex=0\n", encoding="utf-8")
                self._log("[✓] Masaüstü kısayolu oluşturuldu.")

        self._log("\n🎉 İŞLEM BAŞARIYLA TAMAMLANDI!")
        self._log("[*] Kontrol Paneli başlatılıyor: http://localhost:8520")

        # Launch dashboard
        dashboard_script = SCRIPT_DIR / "dashboard.py"
        subprocess.Popen([py_bin, str(dashboard_script), "--vault", str(vault_path), "--open"])

        self._finish(True)

    def _finish(self, success: bool) -> None:
        self.progress.stop()
        self.btn_action.configure(state="normal")
        if success:
            messagebox.showinfo("Başarılı", "İşlem başarıyla tamamlandı ve Kontrol Paneli (Gateway) başlatıldı!")


def main() -> int:
    root = tk.Tk()
    app = SetupWizard(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
